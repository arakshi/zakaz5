from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalyticsEvent, Category, Customer, Order, OrderItem, Product


def dashboard_metrics(db: Session) -> dict:
    today = date.today()
    week = today - timedelta(days=7)
    month = today - timedelta(days=30)

    day_orders = db.scalar(select(func.count(Order.id)).where(func.date(Order.created_at) == today)) or 0
    week_orders = db.scalar(select(func.count(Order.id)).where(Order.created_at >= week)) or 0
    month_orders = db.scalar(select(func.count(Order.id)).where(Order.created_at >= month)) or 0
    month_revenue = float(db.scalar(select(func.sum(Order.total_amount)).where(Order.created_at >= month)) or 0)
    avg_check = float(db.scalar(select(func.avg(Order.total_amount))) or 0)
    new_customers = db.scalar(select(func.count(Customer.id)).where(Customer.created_at >= month)) or 0

    statuses = db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
    payment_methods = db.execute(select(Order.payment_method, func.count(Order.id)).group_by(Order.payment_method)).all()
    pickup_methods = db.execute(select(Order.pickup_method, func.count(Order.id)).group_by(Order.pickup_method)).all()

    top_categories = db.execute(
        select(Category.name, func.count(OrderItem.id))
        .join(Product, Product.category_id == Category.id)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Category.name)
        .order_by(func.count(OrderItem.id).desc())
        .limit(5)
    ).all()

    top_products = db.execute(
        select(Product.name, func.sum(OrderItem.quantity))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    ).all()

    low_stock = db.execute(select(Product.name, Product.stock_quantity).where(Product.stock_quantity <= Product.min_stock).limit(10)).all()

    views = db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.event_type == "view")) or 0
    adds = db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.event_type == "add_to_cart")) or 0
    orders_events = db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.event_type == "order")) or 0

    return {
        "kpi": {
            "day_orders": day_orders,
            "week_orders": week_orders,
            "month_orders": month_orders,
            "month_revenue": month_revenue,
            "avg_check": round(avg_check, 2),
            "new_customers": new_customers,
        },
        "statuses": statuses,
        "payment_methods": payment_methods,
        "pickup_methods": pickup_methods,
        "top_categories": top_categories,
        "top_products": top_products,
        "low_stock": low_stock,
        "conversion": {"views": views, "adds": adds, "orders": orders_events},
    }
