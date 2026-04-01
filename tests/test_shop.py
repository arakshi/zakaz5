from datetime import date, timedelta

from sqlalchemy import select

from app.models import Product, PromoCode
from app.services.auth_service import authenticate
from app.services.order_service import calc_delivery_price


def test_create_product_exists(db_session):
    product = db_session.scalar(select(Product).where(Product.slug == "product-1"))
    assert product is not None


def test_add_to_cart(client):
    resp = client.post("/cart/add", data={"product_id": 1, "qty": 2}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Корзина" in resp.text


def test_apply_promo(client, db_session):
    promo = db_session.scalar(select(PromoCode).limit(1))
    resp = client.post("/cart/apply-promo", data={"code": promo.code}, follow_redirects=False)
    assert resp.status_code == 303


def test_delivery_calc():
    assert calc_delivery_price(7000, 300) == 0
    assert calc_delivery_price(3500, 300) == 300


def test_authorization(db_session):
    user = authenticate(db_session, "admin", "admin123")
    assert user is not None


def test_role_protected(client):
    resp = client.get("/admin")
    assert resp.status_code in (403, 500)


def test_checkout_flow(client):
    client.post("/cart/add", data={"product_id": 2, "qty": 1})
    data = {
        "name": "Тест",
        "phone": "+79990001122",
        "email": "test@example.com",
        "address": "Москва",
        "delivery_date": (date.today() + timedelta(days=1)).isoformat(),
        "delivery_slot_id": 1,
        "delivery_zone_id": 1,
        "payment_method": "card",
        "pickup_method": "delivery",
    }
    resp = client.post("/checkout", data=data, follow_redirects=True)
    assert resp.status_code == 200
    assert "Заказ успешно оформлен" in resp.text
