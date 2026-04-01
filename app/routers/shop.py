import logging
from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AnalyticsEvent, Category, Customer, DeliverySlot, DeliveryZone, Order, Product
from app.schemas.order import OrderCreate
from app.services.cart_service import add_to_cart, cart_totals, update_cart
from app.services.order_service import create_order, validate_promo

router = APIRouter(tags=["shop"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    popular = db.scalars(select(Product).where(Product.is_popular.is_(True), Product.is_active.is_(True)).limit(8)).all()
    promo = db.scalars(select(Product).where(Product.is_promo.is_(True), Product.is_active.is_(True)).limit(8)).all()
    return templates.TemplateResponse("shop/home.html", {"request": request, "popular": popular, "promo": promo})


@router.get("/catalog")
def catalog(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        stmt = stmt.where(or_(Product.name.ilike(f"%{q}%"), Product.description.ilike(f"%{q}%")))
    if category:
        stmt = stmt.join(Category).where(Category.slug == category)
    products = db.scalars(stmt.limit(60)).all()
    categories = db.scalars(select(Category)).all()
    return templates.TemplateResponse(
        "shop/catalog.html",
        {"request": request, "products": products, "categories": categories, "query": q or "", "selected_category": category},
    )


@router.get("/product/{slug}")
def product_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if not product:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
    db.add(AnalyticsEvent(event_type="view", product_id=product.id))
    db.commit()
    recommended = db.scalars(select(Product).where(Product.category_id == product.category_id, Product.id != product.id).limit(4)).all()
    return templates.TemplateResponse("shop/product_detail.html", {"request": request, "product": product, "recommended": recommended})


@router.post("/cart/add")
def cart_add(request: Request, product_id: int = Form(...), qty: int = Form(1), db: Session = Depends(get_db)):
    add_to_cart(request.session, product_id, qty)
    db.add(AnalyticsEvent(event_type="add_to_cart", product_id=product_id))
    db.commit()
    return RedirectResponse("/cart", status_code=303)


@router.get("/cart")
def cart_page(request: Request, db: Session = Depends(get_db)):
    totals = cart_totals(db, request.session, request.session.get("promo_code"))
    return templates.TemplateResponse("shop/cart.html", {"request": request, "totals": totals})


@router.post("/cart/update")
def cart_update(request: Request, product_id: int = Form(...), qty: int = Form(...)):
    update_cart(request.session, product_id, qty)
    return RedirectResponse("/cart", status_code=303)


@router.post("/cart/apply-promo")
def apply_promo(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    promo = validate_promo(db, code)
    if promo:
        request.session["promo_code"] = code
    return RedirectResponse("/cart", status_code=303)


@router.get("/checkout")
def checkout_page(request: Request, db: Session = Depends(get_db)):
    zones = db.scalars(select(DeliveryZone)).all()
    slots = db.scalars(select(DeliverySlot).where(DeliverySlot.is_active.is_(True))).all()
    return templates.TemplateResponse("shop/checkout.html", {"request": request, "zones": zones, "slots": slots, "today": date.today().isoformat()})


@router.post("/checkout")
def checkout(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    address: str = Form(...),
    delivery_date: date = Form(...),
    delivery_slot_id: int | None = Form(default=None),
    delivery_zone_id: int | None = Form(default=None),
    payment_method: str = Form(...),
    pickup_method: str = Form(...),
    comment: str | None = Form(default=None),
    card_text: str | None = Form(default=None),
):
    zone_price = 0
    if delivery_zone_id:
        zone = db.get(DeliveryZone, delivery_zone_id)
        zone_price = zone.price if zone else 0

    try:
        payload = OrderCreate(
            name=name,
            phone=phone,
            email=email,
            address=address,
            delivery_date=delivery_date,
            delivery_slot_id=delivery_slot_id,
            delivery_zone_id=delivery_zone_id,
            zone_price=zone_price,
            payment_method=payment_method,
            pickup_method=pickup_method,
            comment=comment,
            card_text=card_text,
            promo_code=request.session.get("promo_code"),
        ).model_dump()

        order = create_order(db, payload, request.session)
        db.add(AnalyticsEvent(event_type="order", customer_id=order.customer_id))
        db.commit()
        return RedirectResponse(f"/order/success/{order.order_number}", status_code=303)
    except ValidationError as exc:
        zones = db.scalars(select(DeliveryZone)).all()
        slots = db.scalars(select(DeliverySlot).where(DeliverySlot.is_active.is_(True))).all()
        message = "; ".join([err.get("msg", "Ошибка валидации") for err in exc.errors()])
        return templates.TemplateResponse(
            "shop/checkout.html",
            {"request": request, "zones": zones, "slots": slots, "today": date.today().isoformat(), "error": message},
            status_code=400,
        )
    except ValueError as exc:
        zones = db.scalars(select(DeliveryZone)).all()
        slots = db.scalars(select(DeliverySlot).where(DeliverySlot.is_active.is_(True))).all()
        totals = cart_totals(db, request.session, request.session.get("promo_code"))
        return templates.TemplateResponse(
            "shop/checkout.html",
            {"request": request, "zones": zones, "slots": slots, "today": date.today().isoformat(), "error": str(exc), "totals": totals},
            status_code=400,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("checkout_failed", exc_info=exc)
        zones = db.scalars(select(DeliveryZone)).all()
        slots = db.scalars(select(DeliverySlot).where(DeliverySlot.is_active.is_(True))).all()
        return templates.TemplateResponse(
            "shop/checkout.html",
            {"request": request, "zones": zones, "slots": slots, "today": date.today().isoformat(), "error": "Не удалось оформить заказ. Проверьте данные и попробуйте снова."},
            status_code=500,
        )


@router.get("/order/success/{order_number}")
def success_page(order_number: str, request: Request):
    return templates.TemplateResponse("shop/success.html", {"request": request, "order_number": order_number})


@router.get("/my-orders")
def my_orders(request: Request, db: Session = Depends(get_db), phone: str | None = None, email: str | None = None):
    orders = []
    if phone or email:
        customer_stmt = select(Customer)
        if phone:
            customer_stmt = customer_stmt.where(Customer.phone == phone)
        if email:
            customer_stmt = customer_stmt.where(Customer.email == email)
        customer = db.scalar(customer_stmt)
        if customer:
            orders = db.scalars(select(Order).where(Order.customer_id == customer.id).order_by(Order.created_at.desc())).all()
    return templates.TemplateResponse("shop/my_orders.html", {"request": request, "orders": orders})


@router.get("/about")
def about_page(request: Request):
    return templates.TemplateResponse("shop/about.html", {"request": request})


@router.get("/contacts")
def contacts_page(request: Request):
    return templates.TemplateResponse("shop/contacts.html", {"request": request})
