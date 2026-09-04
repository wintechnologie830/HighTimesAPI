from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Customer (read-only view of Aronium data) ----------

class CustomerOut(BaseModel):
    Id: int
    Code: str | None = None
    Name: str
    Email: str | None = None
    PhoneNumber: str | None = None
    City: str | None = None
    IsEnabled: bool


class DocumentOut(BaseModel):
    Id: int
    Number: str
    Date: str
    Total: float
    DocumentTypeName: str
    DocumentTypeCode: str


# ---------- Loyalty / points ----------

class PointsBalanceOut(BaseModel):
    aronium_customer_id: int
    points_balance: float
    point_value_currency: float  # points_balance * redemption value, for convenience


class EarnPointsIn(BaseModel):
    aronium_customer_id: int
    amount_spent: float = Field(gt=0, description="Currency amount the points are based on")
    reference: str | None = Field(
        default=None, description="e.g. Aronium Document Number, to prevent double-earning"
    )
    note: str | None = None


class RedeemPointsIn(BaseModel):
    aronium_customer_id: int
    points: float = Field(gt=0)
    reference: str | None = None
    note: str | None = None


class AdjustPointsIn(BaseModel):
    aronium_customer_id: int
    points: float = Field(description="Positive to add, negative to subtract")
    note: str


class TransactionOut(BaseModel):
    id: int
    type: str
    points: float
    reference: str | None
    note: str | None
    date_created: datetime

    class Config:
        from_attributes = True


class SyncResultOut(BaseModel):
    processed_documents: int
    points_awarded: float
    last_document_id: int
