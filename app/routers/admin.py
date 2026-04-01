import csv
import io

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditLog, Courier, DeliverySlot, DeliveryStatus, DeliveryZone, Order, Product
from app.services.analytics_service import dashboard_metrics
from app.services.auth_service import has_role
from app.services.bootstrap_service import ensure_initial_data
from seed_demo import reset_data, seed_catalog, seed_customers_orders, seed_delivery, seed_promos_events, seed_roles_users

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def guard(request: Request, roles: list[str]):
    if not request.session.get("user_id"):
        return RedirectResponse("/auth/login", status_code=303)
    if not has_role(request, roles):
        return templates.TemplateResponse("errors/403.html", {"request": request}, status_code=403)
    return None


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin", "catalog_manager", "florist", "delivery_manager"])
    if denied:
        return denied
    metrics = dashboard_metrics(db)
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "metrics": metrics})


@router.get("/orders")
def orders_page(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin", "florist", "delivery_manager"])
    if denied:
        return denied
    orders = db.scalars(select(Order).order_by(Order.created_at.desc()).limit(200)).all()
    couriers = db.scalars(select(Courier).where(Courier.is_active.is_(True))).all()
    return templates.TemplateResponse("admin/orders.html", {"request": request, "orders": orders, "couriers": couriers})


@router.post("/orders/{order_id}/assign")
def assign_courier(order_id: int, request: Request, courier_id: int = Form(...), db: Session = Depends(get_db)):
    denied = guard(request, ["admin", "delivery_manager"])
    if denied:
        return denied
    order = db.get(Order, order_id)
    courier = db.get(Courier, courier_id)
    if order and courier:
        order.courier_id = courier.id
        order.delivery_status = DeliveryStatus.assigned
        courier.current_load += 1
        db.add(AuditLog(actor=request.session.get("username", "admin"), action="assign_courier", entity="order", entity_id=order.id))
        db.commit()
    return RedirectResponse("/admin/orders", status_code=303)


@router.get("/products")
def products_page(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin", "catalog_manager"])
    if denied:
        return denied
    products = db.scalars(select(Product).order_by(Product.created_at.desc()).limit(200)).all()
    return templates.TemplateResponse("admin/products.html", {"request": request, "products": products})


@router.post("/products/{product_id}/toggle")
def toggle_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin", "catalog_manager"])
    if denied:
        return denied
    product = db.get(Product, product_id)
    if product:
        product.is_active = not product.is_active
        db.add(AuditLog(actor=request.session.get("username", "admin"), action="toggle_product", entity="product", entity_id=product.id))
        db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin"])
    if denied:
        return denied
    zones = db.scalars(select(DeliveryZone)).all()
    slots = db.scalars(select(DeliverySlot)).all()
    return templates.TemplateResponse("admin/settings.html", {"request": request, "zones": zones, "slots": slots})


@router.get("/logs")
def logs_page(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin"])
    if denied:
        return denied
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300)).all()
    return templates.TemplateResponse("admin/logs.html", {"request": request, "logs": logs})


@router.post("/demo/fill")
def fill_demo(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin"])
    if denied:
        return denied
    reset_data(db)
    # Базовые витрина/каталог + расширенные демо-данные для админ-аналитики
    seed_roles_users(db)
    seed_catalog(db)
    db.commit()
    seed_delivery(db)
    db.commit()
    seed_customers_orders(db)
    seed_promos_events(db)
    db.commit()
    db.add(AuditLog(actor=request.session.get("username", "admin"), action="fill_demo", entity="system"))
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/demo/clear")
def clear_demo(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin"])
    if denied:
        return denied
    reset_data(db)
    # После очистки восстанавливаем базовый рабочий магазин (без массивных демо-заказов)
    ensure_initial_data(db)
    db.add(AuditLog(actor=request.session.get("username", "admin"), action="clear_demo", entity="system"))
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.get("/export/orders.csv")
def export_orders(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin", "delivery_manager"])
    if denied:
        return denied
    orders = db.scalars(select(Order)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_number", "status", "delivery_status", "total_amount", "payment_method", "created_at"])
    for o in orders:
        writer.writerow([o.order_number, o.status.value, o.delivery_status.value, float(o.total_amount), o.payment_method, o.created_at.isoformat()])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=orders.csv"})


@router.get("/export/analytics.csv")
def export_analytics(request: Request, db: Session = Depends(get_db)):
    denied = guard(request, ["admin"])
    if denied:
        return denied
    metrics = dashboard_metrics(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for k, v in metrics["kpi"].items():
        writer.writerow([k, v])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=analytics.csv"})
