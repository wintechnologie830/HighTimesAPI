from pydantic import BaseModel, Field


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
    CustomerId: int | None = None
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
    Quantity: float = 0


class CustomerCreateIn(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None


class StockAdjustIn(BaseModel):
    quantity: int = Field(gt=0)


class StockAdjustOut(BaseModel):
    product_id: int
    quantity_changed: int


class SaleIn(BaseModel):
    customer_id: int | None = None
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)
    payment_type_id: int = 1


class SaleOut(BaseModel):
    document_id: int
    number: str
    total: float
