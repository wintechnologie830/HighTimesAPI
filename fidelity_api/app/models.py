import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, UniqueConstraint, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base

class ProductInventory(Base):
    __tablename__ = "product_inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, unique=True, index=True, nullable=False)
    quantity = Column(Integer, default=0, nullable=False)
    date_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CustomerCredential(Base):
    """
    Sign-in for the loyalty app. Lives ONLY in loyalty.db - Aronium's
    Customer table (in pos.db) has no password column and never should;
    this table just links a name/password to the aronium_customer_id
    that generalAPI created in Aronium at sign-up time.
    """
    __tablename__ = "customer_credentials"

    id = Column(Integer, primary_key=True, index=True)
    aronium_customer_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)


class StaffCredential(Base):
    """
    Sign-in for staff (the pickup desk), completely separate from
    CustomerCredential. Staff never go through Aronium/generalAPI to get
    an account the way customers do at sign-up - there's no matching
    "employee" record anywhere else, this table is the whole account.
    Accounts can be self-registered from the pickup desk's "Create
    account" tab, or provisioned by whoever runs the shop via
    manage_staff.py - either way it's just a row here.
    """
    __tablename__ = "staff_credentials"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # shown to other staff, never to customers
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)


class StaffSession(Base):
    """
    Issued on staff login, required (as X-Staff-Token) to fulfill a
    redemption. This is what lets fulfill() record *which* staff member
    completed a pickup without staff having to re-type their password on
    every single hand-off - they sign in once at the start of a shift.
    """
    __tablename__ = "staff_sessions"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_credentials.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)

    staff = relationship("StaffCredential")


class TransactionType(str, enum.Enum):
    EARN = "EARN"
    REDEEM = "REDEEM"
    ADJUST = "ADJUST"  # manual correction by staff/admin


class RedemptionStatus(str, enum.Enum):
    PENDING = "PENDING"      # points + stock already taken, not picked up yet
    FULFILLED = "FULFILLED"  # staff verified the code and handed over the product


class Redemption(Base):
    """
    One row per points-for-product redemption made in the app. This is the
    paper trail staff need at pickup: the app takes points + stock the
    instant someone taps Redeem, but that customer isn't standing at a
    register when it happens - they're redeeming from home, then walking
    in later. `code` is what they show the cashier; `status` is what lets
    staff tell "already picked up" from "still owed" instead of relying on
    memory.
    """
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("loyalty_accounts.id"), nullable=False)
    product_id = Column(Integer, nullable=False)
    product_name = Column(String, nullable=False)  # snapshotted at redemption time
    quantity = Column(Integer, nullable=False)
    points_spent = Column(Float, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    status = Column(Enum(RedemptionStatus), default=RedemptionStatus.PENDING, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_fulfilled = Column(DateTime, nullable=True)
    # Which staff member marked it picked up. Nullable because it's only
    # ever set at fulfill time - stays NULL for the life of a PENDING
    # redemption. The customer app is only ever shown this raw id (never
    # the name); the staff pickup desk resolves it to staff.name.
    staff_id = Column(Integer, ForeignKey("staff_credentials.id"), nullable=True)

    account = relationship("LoyaltyAccount")
    staff = relationship("StaffCredential")


class LoyaltyAccount(Base):
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
    __tablename__ = "points_transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "reference", "type", name="uq_account_reference_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("loyalty_accounts.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    points = Column(Float, nullable=False)  # positive for EARN, negative for REDEEM
    reference = Column(String, nullable=True)
    note = Column(String, nullable=True)
    date_created = Column(DateTime, default=datetime.utcnow)

    account = relationship("LoyaltyAccount", back_populates="transactions")


class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, index=True)
    last_document_id = Column(Integer, default=0, nullable=False)
