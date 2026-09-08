from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Proxied read-only views (data actually lives behind generalAPI) ----------

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


class ProductOut(BaseModel):
    Id: int
    Name: str
    Code: str | None = None
    Price: float
    IsService: bool


# ---------- Loyalty / points (this is data fidelityAPI actually owns) ----------

class PointsBalanceOut(BaseModel):
    aronium_customer_id: int
    points_balance: float
    point_value_currency: float


class EarnPointsIn(BaseModel):
    aronium_customer_id: int
    amount_spent: float = Field(gt=0)
    reference: str | None = Field(
        default=None, description="e.g. Aronium Document Number, to prevent double-earning"
    )
    note: str | None = None


class RedeemPointsIn(BaseModel):
    aronium_customer_id: int
    points: float = Field(gt=0)
    reference: str | None = None
    note: str | None = None


class RedeemProductIn(BaseModel):
    """Spend points on a specific product instead of a raw point amount.
    The point cost is computed from the product's live price fetched from
    generalAPI, so fidelityAPI never has to keep its own copy of prices."""
    aronium_customer_id: int
    product_id: int
    quantity: int = Field(default=1, gt=0)


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
