from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Proxied read-only views (data actually lives behind generalAPI) ----------

# ---------- Sign up / sign in ----------

class RegisterIn(BaseModel):
    name: str
    password: str = Field(min_length=8)
    phone: str | None = None


class LoginIn(BaseModel):
    name: str
    password: str


class AuthOut(BaseModel):
    aronium_customer_id: int
    name: str


# ---------- Staff sign-in (separate from customer accounts, no Aronium link) ----------

class StaffRegisterIn(BaseModel):
    username: str
    name: str
    password: str = Field(min_length=8)


class StaffLoginIn(BaseModel):
    username: str
    password: str


class StaffAuthOut(BaseModel):
    staff_id: int
    name: str
    token: str


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


class PurchaseProductIn(BaseModel):
    aronium_customer_id: int
    product_id: int
    quantity: int = Field(default=1, gt=0)
    reference: str | None = Field(
        default=None, description="e.g. a POS ticket number, to prevent double-earning"
    )
    note: str | None = None


class RedeemProductIn(BaseModel):
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


class RedeemProductOut(TransactionOut):
    redemption_id: int
    redemption_code: str
    product_name: str
    quantity: int


class RedemptionOut(BaseModel):
    id: int
    code: str
    aronium_customer_id: int | None
    customer_name: str | None
    product_id: int
    product_name: str
    quantity: int
    points_spent: float
    status: str
    date_created: datetime
    date_fulfilled: datetime | None
    staff_id: int | None


class RedemptionStaffOut(RedemptionOut):
    staff_name: str | None


class SyncResultOut(BaseModel):
    processed_documents: int
    points_awarded: float
    last_document_id: int

class ProductOut(BaseModel):
    Id: int
    Name: str
    Code: str | None = None
    Price: float
    IsService: bool
    Quantity: float = 0 
    Inventory: int | None = None
