from datetime import date

from pydantic import BaseModel, EmailStr, Field


class OrderCreate(BaseModel):
    name: str = Field(min_length=2)
    phone: str = Field(min_length=6)
    email: EmailStr
    address: str = Field(min_length=5)
    delivery_date: date
    delivery_slot_id: int | None = None
    delivery_zone_id: int | None = None
    zone_price: int = 0
    comment: str | None = None
    card_text: str | None = None
    payment_method: str
    pickup_method: str
    promo_code: str | None = None
