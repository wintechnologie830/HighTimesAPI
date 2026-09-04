import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class TransactionType(str, enum.Enum):
    EARN = "EARN"
    REDEEM = "REDEEM"
    ADJUST = "ADJUST"  # manual correction by staff/admin


class LoyaltyAccount(Base):
    """
    One row per Aronium customer that participates in the points program.
    `aronium_customer_id` is the Id from Aronium's Customer table — we only
    ever store a reference to it, never a copy of Aronium's own data.
    """
    __tablename__ = "loyalty_accounts"

    id = Column(Integer, primary_key=True, index=True)
    aronium_customer_id = Column(Integer, unique=True, index=True, nullable=False)
    points_balance = Column(Float, default=0.0, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship(
        "PointsTransaction", back_populates="account", cascade="all, delete-orphan"
    )


class PointsTransaction(Base):
    """
    An immutable ledger entry: every earn, redeem, or manual adjustment.
    `reference` is used to store the Aronium Document.Number so a sale can
    never be double-counted into points (see services/points_service.py).
    """
    __tablename__ = "points_transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "reference", "type", name="uq_account_reference_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("loyalty_accounts.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    points = Column(Float, nullable=False)  # positive for EARN, negative for REDEEM
    reference = Column(String, nullable=True)  # e.g. Aronium Document.Number
    note = Column(String, nullable=True)
    date_created = Column(DateTime, default=datetime.utcnow)

    account = relationship("LoyaltyAccount", back_populates="transactions")


class SyncState(Base):
    """
    Tracks the last Aronium Document.Id we've already turned into points,
    so /sync/run can safely be called repeatedly (idempotent).
    """
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, index=True)
    last_document_id = Column(Integer, default=0, nullable=False)
