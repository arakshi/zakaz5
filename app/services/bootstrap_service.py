from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, DeliverySlot, DeliveryZone, Product, PromoCode, Role, User
from app.services.auth_service import hash_password


def ensure_initial_data(db: Session) -> None:
    role_names = ["admin", "catalog_manager", "florist", "delivery_manager"]
    existing_roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for name in role_names:
        if name not in existing_roles:
            role = Role(name=name)
            db.add(role)
            db.flush()
            existing_roles[name] = role

    users = [
        ("admin", "admin123", "Администратор", "admin"),
        ("catalog", "catalog123", "Каталог менеджер", "catalog_manager"),
        ("florist", "florist123", "Флорист", "florist"),
        ("delivery", "delivery123", "Логист", "delivery_manager"),
    ]
    for username, pwd, full_name, role_name in users:
        exists = db.scalar(select(User).where(User.username == username))
        if not exists:
            db.add(User(username=username, password_hash=hash_password(pwd), full_name=full_name, role_id=existing_roles[role_name].id))
        else:
            exists.password_hash = hash_password(pwd)
            exists.role_id = existing_roles[role_name].id
            exists.is_active = True

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
    existing_categories = {c.slug: c for c in db.scalars(select(Category)).all()}
    for name, slug in categories:
        if slug not in existing_categories:
            c = Category(name=name, slug=slug)
            db.add(c)
            db.flush()
            existing_categories[slug] = c

    if not db.scalar(select(Product.id).limit(1)):
        templates = [
            ("bukety", "Букет Розовый закат"),
            ("bukety", "Букет Лавандовое утро"),
            ("monobukety", "Монобукет 51 роза"),
            ("monobukety", "Монобукет Белые пионы"),
            ("flowers-box", "Коробка Нежность"),
            ("flowers-box", "Коробка Романтика"),
            ("baskets", "Корзина Летний сад"),
            ("baskets", "Корзина Полевые цветы"),
            ("gifts", "Подарочный набор Sweet Bloom"),
            ("cards", "Открытка С любовью"),
            ("toys", "Медвежонок Плюш"),
            ("vases", "Ваза Crystal"),
        ]
        for idx in range(1, 25):
            slug, name = templates[idx % len(templates)]
            db.add(
                Product(
                    name=f"{name} {idx}",
                    slug=f"quick-product-{idx}",
                    category_id=existing_categories[slug].id,
                    description="Свежий товар из каталога Bloom.",
                    price=2200 + (idx * 120),
                    old_price=2600 + (idx * 120),
                    composition="Розы, эустома, зелень",
                    color="микс",
                    occasion="праздник",
                    size="M",
                    stock_quantity=20,
                    min_stock=3,
                    is_active=True,
                    is_popular=idx % 3 == 0,
                    is_promo=idx % 4 == 0,
                    image_url=f"https://images.unsplash.com/photo-1526045612212-70caf35c14df?auto=format&fit=crop&w=900&q=80&sig={idx}",
                    is_assembled=False,
                )
            )


    if not db.scalar(select(DeliveryZone.id).limit(1)):
        db.add_all([
            DeliveryZone(name="Центр", price=250),
            DeliveryZone(name="Ближний район", price=390),
            DeliveryZone(name="Дальний район", price=590),
        ])

    if not db.scalar(select(DeliverySlot.id).limit(1)):
        db.add_all([
            DeliverySlot(slot_label="09:00-12:00", max_orders=12, is_active=True),
            DeliverySlot(slot_label="12:00-15:00", max_orders=12, is_active=True),
            DeliverySlot(slot_label="15:00-18:00", max_orders=12, is_active=True),
            DeliverySlot(slot_label="18:00-21:00", max_orders=12, is_active=True),
        ])

    if not db.scalar(select(PromoCode.id).limit(1)):
        today = date.today()
        db.add(PromoCode(code="BLOOM10", discount_percent=10, is_active=True, valid_from=today - timedelta(days=7), valid_to=today + timedelta(days=60)))

    db.commit()
