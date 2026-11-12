"""SMS notifications: per-(problem, recipient) state, queue items and the merged messages sent by the phone."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SmsSubscription(Base):
    """What a recipient was last told about a problem (alarm group or code); survives backend restarts."""

    __tablename__ = "sms_subscription"
    __table_args__ = (UniqueConstraint("problem", "user_id", name="uq_sms_subscription_problem_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sent: Mapped[str | None] = mapped_column(String(10), nullable=True)      # level last sent; None = nothing / cleared
    seen: Mapped[str | None] = mapped_column(String(10), nullable=True)      # effective level now
    changes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    episode_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_text: Mapped[str] = mapped_column(Text, default="", nullable=False)  # for «Снято: …»
    code: Mapped[str] = mapped_column(String(64), default="", nullable=False)  # alarm code behind last_text


class SmsMessage(Base):
    """One SMS as handed to the phone: merged items for one number; immutable once formed."""

    __tablename__ = "sms_message"
    __table_args__ = (Index("ix_sms_message_state_ready", "state", "ready_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)          # ready | leased | sent | failed
    items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ready_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SmsItem(Base):
    """A queue entry: what one recipient should be told about one problem (or a test SMS)."""

    __tablename__ = "sms_item"
    __table_args__ = (
        Index("ix_sms_item_state_ready", "state", "ready_at"),
        Index("ix_sms_item_problem_user", "problem", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    raised: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)           # first | summary | test
    # the journal keeps the row (with the number at creation) when the user is deleted
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)          # pending | formed | superseded | not_needed
    message_id: Mapped[int | None] = mapped_column(ForeignKey("sms_message.id", ondelete="SET NULL"),
                                                   nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ready_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
