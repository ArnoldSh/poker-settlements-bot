from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
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
    checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="inactive")
    requested_chat_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    pending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pending_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_by_telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
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

