from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: float = Field(..., ge=0)
    stock_quantity: int = Field(..., ge=0)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleCreate(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)
    payment_type: Literal["cash", "credit"]
    customer_name: Optional[str] = Field(default=None, max_length=255)
    customer_phone: Optional[str] = Field(default=None, max_length=50)


class Sale(BaseModel):
    id: int
    product_id: int
    debt_id: Optional[int] = None
    quantity: int
    unit_price: float
    total_amount: float
    payment_type: Literal["cash", "credit"]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DebtBase(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    amount_owed: float = Field(..., ge=0)


class DebtCreate(DebtBase):
    pass


class Debt(DebtBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
