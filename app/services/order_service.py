from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AuditLog,
    Customer,
    DeliverySlot,
    DeliveryStatus,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    Product,
    ProductComponent,
    PromoCode,
)
from app.services.cart_service import cart_totals, get_cart


def next_order_number(db: Session) -> str:
    year = date.today().year
    last = db.scalar(select(func.max(Order.id))) or 0
    return f"BLM-{year}-{last + 1:04d}"


def calc_delivery_price(subtotal: Decimal, zone_price: int) -> Decimal:
    if subtotal >= Decimal(settings.free_delivery_from):
        return Decimal("0")
    return Decimal(zone_price)


def validate_slot_available(db: Session, slot_id: int, delivery_date: date) -> None:
    slot = db.get(DeliverySlot, slot_id)
    if not slot or not slot.is_active:
        raise ValueError("Недоступный слот доставки")
    count = db.scalar(select(func.count(Order.id)).where(Order.delivery_slot_id == slot_id, Order.delivery_date == delivery_date))
    if count >= slot.max_orders:
        raise ValueError("Слот перегружен")


def validate_stock(db: Session, product: Product, qty: int) -> None:
    if not product.is_active:
        raise ValueError(f"Товар {product.name} неактивен")
    if product.stock_quantity < qty:
        raise ValueError(f"Недостаточно остатка для {product.name}")
    if product.is_assembled:
        components = db.scalars(select(ProductComponent).where(ProductComponent.product_id == product.id)).all()
        for comp in components:
            c_prod = db.get(Product, comp.component_product_id)
            if not c_prod or c_prod.stock_quantity < comp.quantity * qty:
                raise ValueError(f"Недостаточно компонента {c_prod.name if c_prod else 'unknown'}")


def apply_stock(db: Session, product: Product, qty: int) -> None:
    product.stock_quantity -= qty
    if product.is_assembled:
        components = db.scalars(select(ProductComponent).where(ProductComponent.product_id == product.id)).all()
        for comp in components:
            c_prod = db.get(Product, comp.component_product_id)
            c_prod.stock_quantity -= comp.quantity * qty


def create_order(db: Session, payload: dict, session_data: dict) -> Order:
    totals = cart_totals(db, session_data, payload.get("promo_code"))
    if not totals["items"]:
        raise ValueError("Корзина пуста")

    if payload.get("delivery_slot_id"):
        validate_slot_available(db, int(payload["delivery_slot_id"]), payload["delivery_date"])

    customer = db.query(Customer).filter(Customer.phone == payload["phone"]).first()
    if not customer:
        customer = Customer(name=payload["name"], phone=payload["phone"], email=payload["email"], address=payload["address"])
        db.add(customer)
        db.flush()

    zone_price = int(payload.get("zone_price", settings.base_delivery_cost))
    delivery_price = calc_delivery_price(totals["total"], zone_price)

    order = Order(
        order_number=next_order_number(db),
        customer_id=customer.id,
        status=OrderStatus.new,
        delivery_status=DeliveryStatus.waiting,
        pickup_method=payload["pickup_method"],
        delivery_address=payload["address"],
        delivery_date=payload["delivery_date"],
        delivery_slot_id=payload.get("delivery_slot_id"),
        delivery_zone_id=payload.get("delivery_zone_id"),
        payment_method=payload["payment_method"],
        comment=payload.get("comment"),
        card_text=payload.get("card_text"),
        subtotal=totals["subtotal"],
        discount_amount=totals["discount"],
        delivery_price=delivery_price,
        total_amount=totals["total"] + delivery_price,
    )
    db.add(order)
    db.flush()

    for item in totals["items"]:
        product = item["product"]
        qty = item["qty"]
        validate_stock(db, product, qty)
        apply_stock(db, product, qty)
        db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=qty, price=product.price))

    payment_status = PaymentStatus.pending
    if payload["payment_method"] == "cash":
        payment_status = PaymentStatus.cash_on_delivery

    payment = Payment(order_id=order.id, payment_method=payload["payment_method"], status=payment_status, amount=order.total_amount)
    db.add(payment)

    db.add(AuditLog(actor="customer", action="create_order", entity="order", entity_id=order.id, details=order.order_number))
    session_data["cart"] = {}
    session_data["promo_code"] = None

    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, order: Order) -> None:
    order_items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    for item in order_items:
        product = db.get(Product, item.product_id)
        if product:
            product.stock_quantity += item.quantity
    order.status = OrderStatus.cancelled
    db.add(AuditLog(actor="manager", action="cancel_order", entity="order", entity_id=order.id))
    db.commit()


def validate_promo(db: Session, code: str) -> PromoCode | None:
    promo = db.query(PromoCode).filter_by(code=code, is_active=True).first()
    if not promo:
        return None
    today = date.today()
    if promo.valid_from <= today <= promo.valid_to:
        return promo
    return None
