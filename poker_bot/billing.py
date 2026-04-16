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

ACTIVE_SUBSCRIPTION_STATUSES = {"active"}
PENDING_SUBSCRIPTION_STATUSES = {"pending_activation"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    telegram_user_id: int
    status: str
    provider: str
    provider_status: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    checkout_session_id: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    requested_chat_id: int | None
    pending_since: datetime | None
    cancel_requested_at: datetime | None

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
                    provider="stripe",
                    provider_status=None,
                    current_period_start=None,
                    current_period_end=None,
                    checkout_session_id=None,
                    stripe_customer_id=None,
                    stripe_subscription_id=None,
                    requested_chat_id=None,
                    pending_since=None,
                    cancel_requested_at=None,
                )

            return self._snapshot(subscription)

    def refresh_subscription(self, telegram_user_id: int) -> SubscriptionSnapshot:
        with self.session_factory.begin() as session:
            subscription = session.scalar(
                select(UserSubscriptionModel).where(UserSubscriptionModel.telegram_user_id == telegram_user_id)
            )
            if subscription is None:
                return self.get_subscription(telegram_user_id)

            if subscription.stripe_subscription_id:
                self._sync_subscription_from_stripe(
                    session,
                    telegram_user_id=telegram_user_id,
                    stripe_subscription_id=subscription.stripe_subscription_id,
                    customer_id=subscription.stripe_customer_id,
                )
                session.flush()
                session.refresh(subscription)
                return self._snapshot(subscription)

            if subscription.checkout_session_id:
                stripe_subscription_id, customer_id = self._retrieve_checkout_subscription(subscription.checkout_session_id)
                if stripe_subscription_id:
                    self._sync_subscription_from_stripe(
                        session,
                        telegram_user_id=telegram_user_id,
                        stripe_subscription_id=stripe_subscription_id,
                        customer_id=customer_id or subscription.stripe_customer_id,
                    )
                    session.flush()
                    session.refresh(subscription)
                    return self._snapshot(subscription)

            return self._snapshot(subscription)

    def create_checkout_session(
        self,
        telegram_user_id: int,
        chat_id: int,
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
            subscription.provider = "stripe"
            subscription.status = "pending_activation"
            subscription.provider_status = "checkout_session_created"
            subscription.checkout_session_id = checkout_session["id"]
            subscription.requested_chat_id = chat_id
            subscription.pending_since = datetime.now(timezone.utc)
            subscription.last_pending_reminder_at = None
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

    def mark_cancel_requested(
        self,
        telegram_user_id: int,
        requested_by_telegram_user_id: int,
    ) -> SubscriptionSnapshot:
        with self.session_factory.begin() as session:
            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.cancel_requested_at = datetime.now(timezone.utc)
            subscription.cancel_requested_by_telegram_user_id = requested_by_telegram_user_id

        return self.get_subscription(telegram_user_id)

    def list_pending_reminders(
        self,
        now: datetime | None = None,
        reminder_interval: timedelta = timedelta(hours=24),
    ) -> list[SubscriptionSnapshot]:
        now = now or datetime.now(timezone.utc)
        with self.session_factory() as session:
            subscriptions = session.scalars(
                select(UserSubscriptionModel).where(UserSubscriptionModel.status.in_(PENDING_SUBSCRIPTION_STATUSES))
            ).all()

            results: list[SubscriptionSnapshot] = []
            for subscription in subscriptions:
                if subscription.pending_since is None:
                    continue
                if subscription.pending_since > now - reminder_interval:
                    continue
                if (
                    subscription.last_pending_reminder_at is not None
                    and subscription.last_pending_reminder_at > now - reminder_interval
                ):
                    continue
                results.append(self._snapshot(subscription))
            return results

    def mark_pending_reminder_sent(
        self,
        telegram_user_id: int,
        reminded_at: datetime | None = None,
    ) -> None:
        reminded_at = reminded_at or datetime.now(timezone.utc)
        with self.session_factory.begin() as session:
            subscription = session.scalar(
                select(UserSubscriptionModel).where(UserSubscriptionModel.telegram_user_id == telegram_user_id)
            )
            if subscription is None:
                return
            subscription.last_pending_reminder_at = reminded_at

    def expire_stale_pending_subscriptions(
        self,
        now: datetime | None = None,
        expiration_window: timedelta = timedelta(days=7),
    ) -> list[SubscriptionSnapshot]:
        now = now or datetime.now(timezone.utc)
        with self.session_factory.begin() as session:
            subscriptions = session.scalars(
                select(UserSubscriptionModel).where(UserSubscriptionModel.status.in_(PENDING_SUBSCRIPTION_STATUSES))
            ).all()

            expired: list[SubscriptionSnapshot] = []
            for subscription in subscriptions:
                if subscription.pending_since is None:
                    continue
                if subscription.pending_since > now - expiration_window:
                    continue

                if self.enabled and subscription.stripe_subscription_id:
                    try:
                        stripe.Subscription.cancel(subscription.stripe_subscription_id)
                    except Exception:
                        logger.exception(
                            "failed to cancel stale stripe subscription: telegram_user_id=%s subscription_id=%s",
                            subscription.telegram_user_id,
                            subscription.stripe_subscription_id,
                        )

                subscription.status = "expired"
                subscription.provider_status = subscription.provider_status or "expired_unpaid"
                subscription.current_period_start = None
                subscription.current_period_end = None
                expired.append(self._snapshot(subscription))

            return expired

    def _handle_event(self, session: Session, event) -> None:
        event_type = event["type"]
        payload = event["data"]["object"]
        logger.info("stripe event handler: type=%s", event_type)

        if event_type == "checkout.session.completed":
            telegram_user_id = self._parse_telegram_user_id(
                payload.get("client_reference_id") or payload.get("metadata", {}).get("telegram_user_id")
            )
            stripe_subscription_id = payload.get("subscription")
            customer_id = payload.get("customer")
            if telegram_user_id is None:
                return

            self._ensure_user_row(session, telegram_user_id)
            if stripe_subscription_id:
                self._sync_subscription_from_stripe(
                    session,
                    telegram_user_id=telegram_user_id,
                    stripe_subscription_id=stripe_subscription_id,
                    customer_id=customer_id,
                )
                return

            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.provider = "stripe"
            subscription.provider_status = "checkout_completed"
            subscription.status = "pending_activation"
            subscription.stripe_customer_id = customer_id
            subscription.checkout_session_id = payload.get("id")
            return

        if event_type.startswith("customer.subscription."):
            customer_id = payload.get("customer")
            stripe_subscription_id = payload.get("id")
            telegram_user_id = self._parse_telegram_user_id(payload.get("metadata", {}).get("telegram_user_id"))

            if telegram_user_id is None and customer_id:
                existing = session.scalar(
                    select(UserSubscriptionModel).where(UserSubscriptionModel.stripe_customer_id == customer_id)
                )
                if existing is not None:
                    telegram_user_id = existing.telegram_user_id

            if telegram_user_id is None or not stripe_subscription_id:
                return

            self._ensure_user_row(session, telegram_user_id)
            self._sync_subscription_from_stripe(
                session,
                telegram_user_id=telegram_user_id,
                stripe_subscription_id=stripe_subscription_id,
                customer_id=customer_id,
            )

    def _sync_subscription_from_stripe(
        self,
        session: Session,
        telegram_user_id: int,
        stripe_subscription_id: str,
        customer_id: str | None = None,
    ) -> None:
        stripe_subscription = stripe.Subscription.retrieve(
            stripe_subscription_id,
            expand=["items.data.price"],
        )
        subscription = self._ensure_subscription_row(session, telegram_user_id)
        subscription.provider = "stripe"
        subscription.provider_status = stripe_subscription.get("status")
        subscription.stripe_subscription_id = stripe_subscription.get("id")
        subscription.stripe_customer_id = customer_id or stripe_subscription.get("customer")
        subscription.stripe_price_id = self._extract_price_id(stripe_subscription)
        subscription.current_period_start = self._ts_to_dt(stripe_subscription.get("current_period_start"))
        subscription.current_period_end = self._ts_to_dt(stripe_subscription.get("current_period_end"))
        subscription.status = self._map_provider_status(subscription.provider_status)

        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES:
            subscription.pending_since = None
            subscription.last_pending_reminder_at = None
        elif subscription.status in PENDING_SUBSCRIPTION_STATUSES:
            subscription.pending_since = subscription.pending_since or datetime.now(timezone.utc)

    def _retrieve_checkout_subscription(self, checkout_session_id: str) -> tuple[str | None, str | None]:
        checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)
        return checkout_session.get("subscription"), checkout_session.get("customer")

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
                provider="stripe",
                status="inactive",
            )
            session.add(subscription)
            session.flush()
        return subscription

    @staticmethod
    def _map_provider_status(provider_status: str | None) -> str:
        if provider_status in {"active", "trialing"}:
            return "active"
        if provider_status == "incomplete":
            return "pending_activation"
        if provider_status in {"past_due", "unpaid", "paused"}:
            return "payment_problem"
        if provider_status == "canceled":
            return "canceled"
        if provider_status == "incomplete_expired":
            return "expired"
        return "inactive"

    @staticmethod
    def _extract_price_id(payload) -> str | None:
        items = payload.get("items", {}).get("data", [])
        if items:
            return items[0].get("price", {}).get("id")
        return None

    @staticmethod
    def _ts_to_dt(value: int | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc)

    @staticmethod
    def _parse_telegram_user_id(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _snapshot(subscription: UserSubscriptionModel) -> SubscriptionSnapshot:
        return SubscriptionSnapshot(
            telegram_user_id=subscription.telegram_user_id,
            status=subscription.status,
            provider=subscription.provider,
            provider_status=subscription.provider_status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            checkout_session_id=subscription.checkout_session_id,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            requested_chat_id=subscription.requested_chat_id,
            pending_since=subscription.pending_since,
            cancel_requested_at=subscription.cancel_requested_at,
        )
