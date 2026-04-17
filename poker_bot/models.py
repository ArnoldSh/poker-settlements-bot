from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TelegramUserModel(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger(), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    subscription: Mapped["UserSubscriptionModel | None"] = relationship(back_populates="user", uselist=False)


class ChatGameModel(Base):
    __tablename__ = "chat_games"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(sa.BigInteger(), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_by_telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    finalized_by_telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    players: Mapped[list["GamePlayerModel"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="GamePlayerModel.id",
    )


class GamePlayerModel(Base):
    __tablename__ = "game_players"
    __table_args__ = (UniqueConstraint("game_id", "player_name", name="uq_game_player_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("chat_games.id", ondelete="CASCADE"), index=True)
    player_name: Mapped[str] = mapped_column(String(255))
    buyin: Mapped[float] = mapped_column(Numeric(12, 2))
    out: Mapped[float] = mapped_column(Numeric(12, 2))

    game: Mapped[ChatGameModel] = relationship(back_populates="players")


class UserSubscriptionModel(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger(), ForeignKey("telegram_users.telegram_user_id"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="stripe")
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="inactive")
    requested_chat_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    pending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pending_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_by_telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    cancel_requested_chat_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    refund_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_requested_by_telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    refund_requested_chat_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[TelegramUserModel] = relationship(back_populates="subscription")


class StripeEventModel(Base):
    __tablename__ = "stripe_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(255))
    object_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(64), default="processed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SavedGroupModel(Base):
    __tablename__ = "saved_groups"
    __table_args__ = (UniqueConstraint("owner_telegram_user_id", "name", name="uq_saved_group_owner_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger(), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    members: Mapped[list["SavedGroupMemberModel"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="SavedGroupMemberModel.id",
    )


class SavedGroupMemberModel(Base):
    __tablename__ = "saved_group_members"
    __table_args__ = (UniqueConstraint("group_id", "player_name", name="uq_saved_group_member_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("saved_groups.id", ondelete="CASCADE"), index=True)
    player_name: Mapped[str] = mapped_column(String(255))

    group: Mapped[SavedGroupModel] = relationship(back_populates="members")


class ProductMetricEventModel(Base):
    __tablename__ = "product_metric_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), index=True, nullable=True)
    chat_id: Mapped[int | None] = mapped_column(sa.BigInteger(), index=True, nullable=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("chat_games.id", ondelete="SET NULL"), nullable=True)
    properties_json: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

