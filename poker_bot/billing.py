from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from poker_bot.config import Settings
from poker_bot.models import StripeEventModel, TelegramUserModel, UserSubscriptionModel

ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    telegram_user_id: int
    status: str
    current_period_end: datetime | None
    checkout_session_id: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None

    @property
    def is_active(self) -> bool:
        if self.status not in ACTIVE_SUBSCRIPTION_STATUSES:
            return False
        if self.current_period_end is None:
            return True
        return self.current_period_end >= datetime.now(timezone.utc)


class StripeBillingService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]) -> None:
        self.settings = settings
        self.session_factory = session_factory
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key

    @property
    def enabled(self) -> bool:
        return self.settings.stripe_enabled

    def ensure_user(
        self,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> None:
        with self.session_factory.begin() as session:
            user = session.scalar(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == telegram_user_id)
            )
            if user is None:
                session.add(
                    TelegramUserModel(
                        telegram_user_id=telegram_user_id,
                        username=username,
                        first_name=first_name,
                    )
                )
                return

            user.username = username
            user.first_name = first_name

    def get_subscription(self, telegram_user_id: int) -> SubscriptionSnapshot:
        with self.session_factory() as session:
            subscription = session.scalar(
                select(UserSubscriptionModel).where(UserSubscriptionModel.telegram_user_id == telegram_user_id)
            )

            if subscription is None:
                return SubscriptionSnapshot(
                    telegram_user_id=telegram_user_id,
                    status="inactive",
                    current_period_end=None,
                    checkout_session_id=None,
                    stripe_customer_id=None,
                    stripe_subscription_id=None,
                )

            return SubscriptionSnapshot(
                telegram_user_id=telegram_user_id,
                status=subscription.status,
                current_period_end=subscription.current_period_end,
                checkout_session_id=subscription.checkout_session_id,
                stripe_customer_id=subscription.stripe_customer_id,
                stripe_subscription_id=subscription.stripe_subscription_id,
            )

    def has_active_subscription(self, telegram_user_id: int) -> bool:
        return self.get_subscription(telegram_user_id).is_active

    def create_checkout_session(
        self,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured.")

        with self.session_factory.begin() as session:
            user = self._ensure_user_row(session, telegram_user_id, username, first_name)
            customer_id = user.stripe_customer_id
            if not customer_id:
                customer = stripe.Customer.create(
                    metadata={"telegram_user_id": str(telegram_user_id)},
                    name=first_name or username or str(telegram_user_id),
                )
                customer_id = customer["id"]
                user.stripe_customer_id = customer_id

            checkout_session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": self.settings.stripe_price_id, "quantity": 1}],
                client_reference_id=str(telegram_user_id),
                success_url=f"{self.settings.app_base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{self.settings.app_base_url}/billing/cancel",
                allow_promotion_codes=True,
                metadata={"telegram_user_id": str(telegram_user_id)},
                subscription_data={"metadata": {"telegram_user_id": str(telegram_user_id)}},
            )

            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.checkout_session_id = checkout_session["id"]
            subscription.stripe_customer_id = customer_id
            subscription.stripe_price_id = self.settings.stripe_price_id

            return checkout_session["url"]

    def process_webhook(self, payload: bytes, signature: str | None) -> dict[str, str]:
        if not self.settings.stripe_webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET is required to process Stripe webhooks.")

        event = stripe.Webhook.construct_event(payload, signature, self.settings.stripe_webhook_secret)
        event_id = event["id"]
        logger.info("stripe webhook received: type=%s event_id=%s", event["type"], event_id)

        with self.session_factory.begin() as session:
            existing = session.scalar(select(StripeEventModel).where(StripeEventModel.event_id == event_id))
            if existing is not None:
                logger.info("stripe webhook skipped: duplicate event_id=%s", event_id)
                return {"event_id": event_id, "status": "already_processed"}

            session.add(
                StripeEventModel(
                    event_id=event_id,
                    event_type=event["type"],
                    processing_status="processed",
                    payload_json=json.dumps(event, default=str),
                )
            )
            self._handle_event(session, event)

        logger.info("stripe webhook processed: event_id=%s", event_id)
        return {"event_id": event_id, "status": "processed"}

    def force_subscription(
        self,
        telegram_user_id: int,
        status: str,
        days: int | None = None,
    ) -> SubscriptionSnapshot:
        with self.session_factory.begin() as session:
            self._ensure_user_row(session, telegram_user_id)
            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.status = status
            subscription.current_period_end = (
                datetime.now(timezone.utc) + timedelta(days=days) if days is not None else None
            )

        return self.get_subscription(telegram_user_id)

    def debug_user_payload(self, telegram_user_id: int) -> dict[str, object]:
        with self.session_factory() as session:
            user = session.scalar(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == telegram_user_id)
            )
            subscription = session.scalar(
                select(UserSubscriptionModel).where(UserSubscriptionModel.telegram_user_id == telegram_user_id)
            )

            return {
                "user": None
                if user is None
                else {
                    "telegram_user_id": user.telegram_user_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "stripe_customer_id": user.stripe_customer_id,
                },
                "subscription": None
                if subscription is None
                else {
                    "status": subscription.status,
                    "current_period_end": None
                    if subscription.current_period_end is None
                    else subscription.current_period_end.isoformat(),
                    "stripe_customer_id": subscription.stripe_customer_id,
                    "stripe_subscription_id": subscription.stripe_subscription_id,
                    "checkout_session_id": subscription.checkout_session_id,
                    "stripe_price_id": subscription.stripe_price_id,
                },
            }

    def _handle_event(self, session: Session, event) -> None:
        event_type = event["type"]
        payload = event["data"]["object"]
        logger.info("stripe event handler: type=%s", event_type)

        if event_type == "checkout.session.completed":
            telegram_user_id = self._parse_telegram_user_id(payload.get("client_reference_id") or payload.get("metadata", {}).get("telegram_user_id"))
            if telegram_user_id is None:
                return

            user = self._ensure_user_row(session, telegram_user_id)
            customer_id = payload.get("customer")
            if customer_id:
                user.stripe_customer_id = customer_id

            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.checkout_session_id = payload.get("id")
            subscription.stripe_customer_id = customer_id
            subscription.stripe_subscription_id = payload.get("subscription")
            subscription.status = "checkout_completed"
            return

        if event_type.startswith("customer.subscription."):
            customer_id = payload.get("customer")
            telegram_user_id = self._parse_telegram_user_id(payload.get("metadata", {}).get("telegram_user_id"))
            subscription = None

            if telegram_user_id is not None:
                self._ensure_user_row(session, telegram_user_id)
                subscription = self._ensure_subscription_row(session, telegram_user_id)
            elif customer_id:
                subscription = session.scalar(
                    select(UserSubscriptionModel).where(UserSubscriptionModel.stripe_customer_id == customer_id)
                )

            if subscription is None:
                return

            subscription.stripe_customer_id = customer_id
            subscription.stripe_subscription_id = payload.get("id")
            subscription.stripe_price_id = self._extract_price_id(payload)
            subscription.status = payload.get("status", "inactive")

            current_period_end = payload.get("current_period_end")
            if current_period_end:
                subscription.current_period_end = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
            else:
                subscription.current_period_end = None

    def _ensure_user_row(
        self,
        session: Session,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> TelegramUserModel:
        user = session.scalar(select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == telegram_user_id))
        if user is None:
            user = TelegramUserModel(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
            )
            session.add(user)
            session.flush()
        else:
            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name
        return user

    def _ensure_subscription_row(self, session: Session, telegram_user_id: int) -> UserSubscriptionModel:
        subscription = session.scalar(
            select(UserSubscriptionModel).where(UserSubscriptionModel.telegram_user_id == telegram_user_id)
        )
        if subscription is None:
            subscription = UserSubscriptionModel(
                telegram_user_id=telegram_user_id,
                status="inactive",
            )
            session.add(subscription)
            session.flush()
        return subscription

    @staticmethod
    def _extract_price_id(payload) -> str | None:
        items = payload.get("items", {}).get("data", [])
        if items:
            return items[0].get("price", {}).get("id")
        return None

    @staticmethod
    def _parse_telegram_user_id(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
