from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models import (
    AnalyticsEvent,
    AuditLog,
    Category,
    Courier,
    Customer,
    DeliverySlot,
    DeliveryStatus,
    DeliveryZone,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    PickupMethod,
    Product,
    PromoCode,
    Role,
    User,
)
from app.services.auth_service import hash_password


def reset_data(db):
    for model in [Payment, OrderItem, Order, AnalyticsEvent, AuditLog, Product, Category, Customer, Courier, DeliveryZone, DeliverySlot, PromoCode, User, Role]:
        db.execute(delete(model))
    db.commit()


def seed_roles_users(db):
    roles = {}
    for name in ["admin", "catalog_manager", "florist", "delivery_manager"]:
        role = Role(name=name)
        db.add(role)
        db.flush()
        roles[name] = role

    users = [
        ("admin", "admin123", "Администратор", "admin"),
        ("catalog", "catalog123", "Каталог менеджер", "catalog_manager"),
        ("florist", "florist123", "Флорист", "florist"),
        ("delivery", "delivery123", "Логист", "delivery_manager"),
    ]
    for username, pwd, full_name, role in users:
        db.add(User(username=username, password_hash=hash_password(pwd), full_name=full_name, role_id=roles[role].id))


def seed_catalog(db):
    categories = [
        ("Букеты", "bukety"),
        ("Монобукеты", "monobukety"),
        ("Цветы в коробках", "flowers-box"),
        ("Композиции в корзинах", "baskets"),
        ("Подарки", "gifts"),
        ("Открытки", "cards"),
        ("Мягкие игрушки", "toys"),
        ("Вазы", "vases"),
    ]
    cat_objs = []
    for n, s in categories:
        c = Category(name=n, slug=s)
        db.add(c)
        db.flush()
        cat_objs.append(c)

    catalog_by_category = {
        "bukety": ["Рассветный сад", "Персиковое облако", "Летний ветер", "Утренний туман"],
        "monobukety": ["101 красная роза", "Белые пионы", "Тюльпаны крем", "Розы Эквадор"],
        "flowers-box": ["Коробка Розовый шёлк", "Коробка Лавандовый вечер", "Коробка Нежность"],
        "baskets": ["Корзина Лесная поляна", "Корзина Сканди", "Корзина Сирень"],
        "gifts": ["Подарочный набор Sweet Bloom", "Сет с макарунами", "Шоколадный комплимент"],
        "cards": ["Открытка С любовью", "Открытка Для мамы", "Открытка Поздравляем"],
        "toys": ["Медвежонок Бруно", "Зайка Лили", "Котик Мяу"],
        "vases": ["Ваза Crystal", "Ваза Minimal", "Ваза Botanica"],
    }
    image_pool = [
        "https://images.unsplash.com/photo-1526045612212-70caf35c14df",
        "https://images.unsplash.com/photo-1490750967868-88aa4486c946",
        "https://images.unsplash.com/photo-1468327768560-75b778cbb551",
        "https://images.unsplash.com/photo-1561181286-d3fee7d55364",
        "https://images.unsplash.com/photo-1487070183336-b863922373d4",
    ]

    idx = 1
    for cat in cat_objs:
        names = catalog_by_category.get(cat.slug, [cat.name])
        for _ in range(6):
            name = f"{random.choice(names)} {idx}"
            db.add(
                Product(
                    name=name,
                    slug=f"product-{idx}",
                    category_id=cat.id,
                    description="Свежая композиция от флористов с аккуратной упаковкой.",
                    price=random.randint(1800, 8500),
                    old_price=random.choice([None, random.randint(2000, 9000)]),
                    composition="Розы, эустома, эвкалипт",
                    color=random.choice(["красный", "розовый", "белый", "микс"]),
                    occasion=random.choice(["день рождения", "8 марта", "свадьба", "без повода"]),
                    size=random.choice(["S", "M", "L"]),
                    stock_quantity=random.randint(1, 40),
                    min_stock=random.randint(3, 8),
                    is_active=True,
                    is_popular=idx % 5 == 0,
                    is_promo=idx % 7 == 0,
                    image_url=f"{random.choice(image_pool)}?auto=format&fit=crop&w=900&q=80",
                    is_assembled=idx % 11 == 0,
                )
            )
            idx += 1


def seed_delivery(db):
    zones = [
        ("Центр", 250),
        ("Ближний район", 390),
        ("Дальний район", 590),
    ]
    for n, p in zones:
        db.add(DeliveryZone(name=n, price=p))

    for s in ["09:00-12:00", "12:00-15:00", "15:00-18:00", "18:00-21:00"]:
        db.add(DeliverySlot(slot_label=s, max_orders=12, is_active=True))

    names = ["Иван Курьер", "Олег Доставка", "Никита Логист", "Максим Водитель", "Егор Экспресс", "Роман Быстрый"]
    for i, n in enumerate(names, start=1):
        db.add(Courier(name=n, phone=f"+79001000{i:02d}", status=random.choice(["free", "busy"]), is_active=True, current_load=random.randint(0, 6)))


def seed_customers_orders(db):
    customers = []
    for i in range(1, 26):
        c = Customer(name=f"Клиент {i}", phone=f"+7900555{i:04d}", email=f"client{i}@mail.ru", address=f"Москва, ул. Цветочная, д. {i}")
        db.add(c)
        db.flush()
        customers.append(c)

    products = db.query(Product).all()
    zones = db.query(DeliveryZone).all()
    slots = db.query(DeliverySlot).all()

    holiday_days = [date(2026, 2, 14), date(2026, 3, 8)]
    for i in range(1, 91):
        c = random.choice(customers)
        created = datetime.now() - timedelta(days=random.randint(1, 120))
        if i % 15 == 0:
            created = datetime.combine(random.choice(holiday_days), datetime.min.time()) + timedelta(hours=random.randint(8, 20))
        status = random.choice(list(OrderStatus))
        delivery_status = random.choice(list(DeliveryStatus))
        zone = random.choice(zones)
        slot = random.choice(slots)
        subtotal = random.randint(2000, 12000)
        discount = random.choice([0, 200, 500, 900])
        delivery_price = 0 if subtotal >= 6000 else zone.price
        total = subtotal - discount + delivery_price

        order = Order(
            order_number=f"BLM-2026-{i:04d}",
            customer_id=c.id,
            status=status,
            delivery_status=delivery_status,
            pickup_method=random.choice(list(PickupMethod)),
            delivery_address=c.address,
            delivery_date=(created + timedelta(days=1)).date(),
            delivery_slot_id=slot.id,
            delivery_zone_id=zone.id,
            payment_method=random.choice(["card", "sbp", "cash"]),
            subtotal=subtotal,
            discount_amount=discount,
            delivery_price=delivery_price,
            total_amount=total,
            created_at=created,
        )
        db.add(order)
        db.flush()

        for _ in range(random.randint(1, 3)):
            p = random.choice(products)
            qty = random.randint(1, 3)
            db.add(OrderItem(order_id=order.id, product_id=p.id, quantity=qty, price=p.price))
            p.stock_quantity = max(0, p.stock_quantity - qty)

        pay_status = random.choice(list(PaymentStatus))
        db.add(Payment(order_id=order.id, payment_method=order.payment_method, status=pay_status, amount=order.total_amount))

    low_stock_products = random.sample(products, 8)
    for p in low_stock_products:
        p.stock_quantity = random.randint(0, p.min_stock)


def seed_promos_events(db):
    today = date.today()
    for i, code in enumerate(["BLOOM5", "SPRING10", "LOVE15", "MARCH8", "WELCOME7", "VIP20"]):
        db.add(PromoCode(code=code, discount_percent=[5, 10, 15, 12, 7, 20][i], is_active=True, valid_from=today - timedelta(days=30), valid_to=today + timedelta(days=30)))

    products = db.query(Product).limit(20).all()
    for _ in range(500):
        p = random.choice(products)
        db.add(AnalyticsEvent(event_type=random.choices(["view", "add_to_cart", "order"], weights=[70, 20, 10])[0], product_id=p.id))


def main():
    db = SessionLocal()
    reset_data(db)
    seed_roles_users(db)
    seed_catalog(db)
    db.commit()
    seed_delivery(db)
    db.commit()
    seed_customers_orders(db)
    seed_promos_events(db)
    db.commit()
    print("Data seeded successfully")


if __name__ == "__main__":
    main()
