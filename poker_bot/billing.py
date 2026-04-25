from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from poker_bot.config import Settings
from poker_bot.i18n import tr
from poker_bot.models import StripeEventModel, TelegramUserModel, UserSubscriptionModel
from poker_bot.notifications import UserChatNotification

ACTIVE_SUBSCRIPTION_STATUSES = {"active"}
PENDING_SUBSCRIPTION_STATUSES = {"pending_activation"}
SUBSCRIPTION_PLAN_CODES = ("monthly", "quarterly", "semiannual", "yearly")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    telegram_user_id: int
    status: str
    provider: str
    provider_status: str | None
    plan_code: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    checkout_session_id: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    requested_chat_id: int | None
    pending_since: datetime | None
    cancel_requested_at: datetime | None
    cancel_requested_chat_id: int | None
    refund_requested_at: datetime | None
    refund_requested_chat_id: int | None

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
                    plan_code=None,
                    current_period_start=None,
                    current_period_end=None,
                    checkout_session_id=None,
                    stripe_customer_id=None,
                    stripe_subscription_id=None,
                    requested_chat_id=None,
                    pending_since=None,
                    cancel_requested_at=None,
                    cancel_requested_chat_id=None,
                    refund_requested_at=None,
                    refund_requested_chat_id=None,
                )

            return self._snapshot(subscription)

    def chat_has_subscription_history(self, chat_id: int) -> bool:
        historical_statuses = {"active", "payment_problem", "canceled", "expired"}
        with self.session_factory() as session:
            return (
                session.scalar(
                    select(UserSubscriptionModel.id).where(
                        (
                            (UserSubscriptionModel.requested_chat_id == chat_id)
                            | (UserSubscriptionModel.cancel_requested_chat_id == chat_id)
                            | (UserSubscriptionModel.refund_requested_chat_id == chat_id)
                        ),
                        UserSubscriptionModel.status.in_(historical_statuses),
                    )
                )
                is not None
            )

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
        plan_code: str,
        username: str | None = None,
        first_name: str | None = None,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured.")
        price_id = self._resolve_price_id(plan_code)

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
                line_items=[{"price": price_id, "quantity": 1}],
                client_reference_id=str(telegram_user_id),
                success_url=f"{self.settings.app_base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{self.settings.app_base_url}/billing/cancel",
                allow_promotion_codes=True,
                metadata={
                    "telegram_user_id": str(telegram_user_id),
                    "plan_code": plan_code,
                },
                subscription_data={
                    "metadata": {
                        "telegram_user_id": str(telegram_user_id),
                        "plan_code": plan_code,
                    }
                },
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
            subscription.stripe_price_id = price_id
            subscription.plan_code = plan_code

            return checkout_session["url"]

    @dataclass(frozen=True)
    class WebhookProcessingResult:
        event_id: str
        event_type: str
        status: str
        notifications: list[UserChatNotification]

    def process_webhook(self, payload: bytes, signature: str | None) -> WebhookProcessingResult:
        if not self.settings.stripe_webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET is required to process Stripe webhooks.")

        event = stripe.Webhook.construct_event(payload, signature, self.settings.stripe_webhook_secret)
        event_id = event["id"]
        logger.info("stripe webhook received: type=%s event_id=%s", event["type"], event_id)

        with self.session_factory.begin() as session:
            existing = session.scalar(select(StripeEventModel).where(StripeEventModel.event_id == event_id))
            if existing is not None:
                logger.info("stripe webhook skipped: duplicate event_id=%s", event_id)
                return self.WebhookProcessingResult(
                    event_id=event_id,
                    event_type=event["type"],
                    status="already_processed",
                    notifications=[],
                )

            session.add(
                StripeEventModel(
                    event_id=event_id,
                    event_type=event["type"],
                    object_type=self._extract_object_type(event["type"]),
                    object_reference_id=self._extract_object_reference_id(event),
                    processing_status="processed",
                )
            )
            notifications = self._handle_event(session, event)

        logger.info("stripe webhook processed: event_id=%s", event_id)
        return self.WebhookProcessingResult(
            event_id=event_id,
            event_type=event["type"],
            status="processed",
            notifications=notifications,
        )

    def mark_cancel_requested(
        self,
        telegram_user_id: int,
        requested_by_telegram_user_id: int,
        source_chat_id: int | None,
    ) -> SubscriptionSnapshot:
        with self.session_factory.begin() as session:
            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.cancel_requested_at = datetime.now(timezone.utc)
            subscription.cancel_requested_by_telegram_user_id = requested_by_telegram_user_id
            subscription.cancel_requested_chat_id = source_chat_id

        return self.get_subscription(telegram_user_id)

    def mark_refund_requested(
        self,
        telegram_user_id: int,
        requested_by_telegram_user_id: int,
        source_chat_id: int | None,
    ) -> SubscriptionSnapshot:
        with self.session_factory.begin() as session:
            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.refund_requested_at = datetime.now(timezone.utc)
            subscription.refund_requested_by_telegram_user_id = requested_by_telegram_user_id
            subscription.refund_requested_chat_id = source_chat_id

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

    def _handle_event(self, session: Session, event) -> list[UserChatNotification]:
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
                return []

            self._ensure_user_row(session, telegram_user_id)
            if stripe_subscription_id:
                previous_snapshot = self._snapshot(self._ensure_subscription_row(session, telegram_user_id))
                subscription = self._sync_subscription_from_stripe(
                    session,
                    telegram_user_id=telegram_user_id,
                    stripe_subscription_id=stripe_subscription_id,
                    customer_id=customer_id,
                )
                return self._build_subscription_notifications(previous_snapshot, subscription, event_type)

            subscription = self._ensure_subscription_row(session, telegram_user_id)
            subscription.provider = "stripe"
            subscription.provider_status = "checkout_completed"
            subscription.status = "pending_activation"
            subscription.stripe_customer_id = customer_id
            subscription.checkout_session_id = payload.get("id")
            subscription.plan_code = payload.get("metadata", {}).get("plan_code")
            return []

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
                return []

            self._ensure_user_row(session, telegram_user_id)
            previous_snapshot = self._snapshot(self._ensure_subscription_row(session, telegram_user_id))
            subscription = self._sync_subscription_from_stripe(
                session,
                telegram_user_id=telegram_user_id,
                stripe_subscription_id=stripe_subscription_id,
                customer_id=customer_id,
            )
            return self._build_subscription_notifications(previous_snapshot, subscription, event_type)

        if event_type in {"charge.refunded", "refund.updated"}:
            customer_id = payload.get("customer")
            if not customer_id and payload.get("charge"):
                try:
                    charge = stripe.Charge.retrieve(payload.get("charge"))
                    customer_id = charge.get("customer")
                except Exception:
                    logger.exception("failed to retrieve charge for refund webhook")
            if not customer_id:
                return []

            subscription = session.scalar(
                select(UserSubscriptionModel).where(UserSubscriptionModel.stripe_customer_id == customer_id)
            )
            if subscription is None:
                return []
            snapshot = self._snapshot(subscription)
            chat_id = snapshot.refund_requested_chat_id or snapshot.requested_chat_id
            if chat_id is None:
                return []
            return [UserChatNotification(chat_id=chat_id, text=tr("subscription_event_refunded"))]

        return []

    def _sync_subscription_from_stripe(
        self,
        session: Session,
        telegram_user_id: int,
        stripe_subscription_id: str,
        customer_id: str | None = None,
    ) -> SubscriptionSnapshot:
        stripe_subscription = stripe.Subscription.retrieve(
            stripe_subscription_id,
            expand=["items.data.price"],
        )
        subscription = self._ensure_subscription_row(session, telegram_user_id)
        subscription.provider = "stripe"
        subscription.provider_status = "paused" if stripe_subscription.get("pause_collection") else stripe_subscription.get("status")
        subscription.stripe_subscription_id = stripe_subscription.get("id")
        subscription.stripe_customer_id = customer_id or stripe_subscription.get("customer")
        subscription.stripe_price_id = self._extract_price_id(stripe_subscription)
        subscription.plan_code = self._extract_plan_code(stripe_subscription)
        subscription.current_period_start = self._ts_to_dt(stripe_subscription.get("current_period_start"))
        subscription.current_period_end = self._ts_to_dt(stripe_subscription.get("current_period_end"))
        subscription.status = self._map_provider_status(subscription.provider_status)

        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES:
            subscription.pending_since = None
            subscription.last_pending_reminder_at = None
        elif subscription.status in PENDING_SUBSCRIPTION_STATUSES:
            subscription.pending_since = subscription.pending_since or datetime.now(timezone.utc)
        return self._snapshot(subscription)

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

    def available_plan_codes(self) -> list[str]:
        return [plan_code for plan_code in SUBSCRIPTION_PLAN_CODES if plan_code in self.settings.stripe_price_ids]

    def _resolve_price_id(self, plan_code: str) -> str:
        price_id = self.settings.stripe_price_ids.get(plan_code)
        if price_id:
            return price_id
        raise ValueError(f"Unsupported subscription plan: {plan_code}")

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

    def _extract_plan_code(self, payload) -> str | None:
        metadata = payload.get("metadata", {}) or {}
        plan_code = metadata.get("plan_code")
        if plan_code in SUBSCRIPTION_PLAN_CODES:
            return plan_code

        price_id = self._extract_price_id(payload)
        for candidate, candidate_price_id in self.settings.stripe_price_ids.items():
            if candidate_price_id == price_id:
                return candidate
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
    def _extract_object_type(event_type: str | None) -> str | None:
        if not event_type:
            return None
        parts = event_type.split(".")
        if len(parts) < 2:
            return event_type
        return ".".join(parts[:-1])

    @staticmethod
    def _extract_object_reference_id(event) -> str | None:
        try:
            return event["data"]["object"].get("id")
        except (KeyError, TypeError, AttributeError):
            return None

    @staticmethod
    def _snapshot(subscription: UserSubscriptionModel) -> SubscriptionSnapshot:
        return SubscriptionSnapshot(
            telegram_user_id=subscription.telegram_user_id,
            status=subscription.status,
            provider=subscription.provider,
            provider_status=subscription.provider_status,
            plan_code=subscription.plan_code,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            checkout_session_id=subscription.checkout_session_id,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            requested_chat_id=subscription.requested_chat_id,
            pending_since=subscription.pending_since,
            cancel_requested_at=subscription.cancel_requested_at,
            cancel_requested_chat_id=subscription.cancel_requested_chat_id,
            refund_requested_at=subscription.refund_requested_at,
            refund_requested_chat_id=subscription.refund_requested_chat_id,
        )

    def _build_subscription_notifications(
        self,
        previous: SubscriptionSnapshot,
        current: SubscriptionSnapshot,
        event_type: str,
    ) -> list[UserChatNotification]:
        chat_id = current.requested_chat_id
        if event_type == "customer.subscription.deleted":
            chat_id = current.cancel_requested_chat_id or current.requested_chat_id
        if chat_id is None:
            return []

        if event_type == "customer.subscription.created":
            if current.status == "pending_activation":
                return [UserChatNotification(chat_id=chat_id, text=tr("subscription_event_started_pending"))]
            if current.status == "active":
                return [
                    UserChatNotification(
                        chat_id=chat_id,
                        text=tr(
                            "subscription_event_paid",
                            plan=tr(f"plan_{current.plan_code or 'monthly'}"),
                            date=self._format_period_end(current.current_period_end),
                        ),
                    )
                ]

        if event_type == "customer.subscription.updated":
            if previous.status != "active" and current.status == "active":
                return [
                    UserChatNotification(
                        chat_id=chat_id,
                        text=tr(
                            "subscription_event_paid",
                            plan=tr(f"plan_{current.plan_code or 'monthly'}"),
                            date=self._format_period_end(current.current_period_end),
                        ),
                    )
                ]
            if previous.status == "active" and current.status == "payment_problem":
                return [UserChatNotification(chat_id=chat_id, text=tr("subscription_event_paused"))]
            if previous.status == "active" and current.status in {"canceled", "expired"}:
                return [UserChatNotification(chat_id=chat_id, text=tr("subscription_event_canceled"))]

        if event_type == "customer.subscription.paused":
            return [UserChatNotification(chat_id=chat_id, text=tr("subscription_event_paused"))]

        if event_type == "customer.subscription.deleted":
            return [UserChatNotification(chat_id=chat_id, text=tr("subscription_event_canceled"))]

        return []

    @staticmethod
    def _format_period_end(value: datetime | None) -> str:
        if value is None:
            return "без даты окончания"
        return value.strftime("%Y-%m-%d %H:%M UTC")
