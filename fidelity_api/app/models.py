import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, UniqueConstraint, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base

class ProductInventory(Base):
    """
    DEPRECATED - no longer read or written anywhere in the app.

    Redeemable stock used to be tracked here as its own counter, separate
    from Aronium's real stock quantity, which let it drift out of sync
    (see services/inventory.py for the full explanation). Redeemable stock
    is now always read live from Aronium instead, so this table is unused.

    The class/table is kept only so existing deployments don't break on
    startup; it's safe to drop once you've confirmed nothing else needs it.
    """

    __tablename__ = "product_inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, unique=True, index=True, nullable=False)
    quantity = Column(Integer, default=0, nullable=False)
    date_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class CustomerCredential(Base):
    __tablename__ = "customer_credentials"

    id = Column(Integer, primary_key=True, index=True)
    aronium_customer_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    date_created = Column(DateTime, default=datetime.now)


class StaffCredential(Base):
    __tablename__ = "staff_credentials"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # shown to other staff, never to customers
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    date_created = Column(DateTime, default=datetime.now)


class StaffSession(Base):
    __tablename__ = "staff_sessions"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_credentials.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    date_created = Column(DateTime, default=datetime.now)

    staff = relationship("StaffCredential")


class TransactionType(str, enum.Enum):
    EARN = "EARN"
    REDEEM = "REDEEM"
    ADJUST = "ADJUST"


class RedemptionStatus(str, enum.Enum):
    PENDING = "PENDING"      
    FULFILLED = "FULFILLED"


class Redemption(Base):
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("loyalty_accounts.id"), nullable=False)
    product_id = Column(Integer, nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    points_spent = Column(Float, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    status = Column(Enum(RedemptionStatus), default=RedemptionStatus.PENDING, nullable=False)
    date_created = Column(DateTime, default=datetime.now)
    date_fulfilled = Column(DateTime, nullable=True)
    staff_id = Column(Integer, ForeignKey("staff_credentials.id"), nullable=True)

    account = relationship("LoyaltyAccount")
    staff = relationship("StaffCredential")


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    id = Column(Integer, primary_key=True, index=True)
    aronium_customer_id = Column(Integer, unique=True, index=True, nullable=False)
    points_balance = Column(Float, default=0.0, nullable=False)
    date_created = Column(DateTime, default=datetime.now)
    date_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    transactions = relationship(
        "PointsTransaction", back_populates="account", cascade="all, delete-orphan"
    )


class PointsTransaction(Base):
    __tablename__ = "points_transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "reference", "type", name="uq_account_reference_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("loyalty_accounts.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    points = Column(Float, nullable=False)
    reference = Column(String, nullable=True)
    note = Column(String, nullable=True)
    date_created = Column(DateTime, default=datetime.now)

    account = relationship("LoyaltyAccount", back_populates="transactions")


class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, index=True)
    last_document_id = Column(Integer, default=0, nullable=False)
