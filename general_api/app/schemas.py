from pydantic import BaseModel


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
