import hashlib

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import User


def _salt() -> str:
    return settings.secret_key or "bloom-secret"


def hash_password(password: str) -> str:
    value = f"{_salt()}::{password}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).options(selectinload(User.role)).where(User.username == username, User.is_active.is_(True)))
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def login_user(request: Request, user: User) -> None:
    role_name = user.role.name if user.role else "admin"

    request.session["user_id"] = user.id
    request.session["role"] = role_name
    request.session["username"] = user.username


def logout_user(request: Request) -> None:
    request.session.clear()


def has_role(request: Request, roles: list[str]) -> bool:
    return request.session.get("role") in roles


def require_role(request: Request, roles: list[str]) -> None:
    if not has_role(request, roles):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
