from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Product, PromoCode


def get_cart(session: dict) -> dict:
    return session.setdefault("cart", {})


def add_to_cart(session: dict, product_id: int, qty: int = 1) -> None:
    cart = get_cart(session)
    key = str(product_id)
    cart[key] = cart.get(key, 0) + qty
    session["cart"] = cart


def update_cart(session: dict, product_id: int, qty: int) -> None:
    cart = get_cart(session)
    key = str(product_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    session["cart"] = cart


def cart_totals(db: Session, session: dict, promo_code: str | None = None) -> dict:
    cart = get_cart(session)
    subtotal = Decimal("0")
    items = []
    for pid, qty in cart.items():
        product = db.get(Product, int(pid))
        if not product:
            continue
        line_total = Decimal(str(product.price)) * qty
        subtotal += line_total
        items.append({"product": product, "qty": qty, "line_total": line_total})

    discount = Decimal("0")
    if promo_code:
        promo = db.query(PromoCode).filter_by(code=promo_code, is_active=True).first()
        if promo:
            discount = subtotal * Decimal(promo.discount_percent) / Decimal("100")
    return {"items": items, "subtotal": subtotal, "discount": discount, "total": subtotal - discount}
