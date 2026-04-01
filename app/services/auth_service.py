from fastapi import HTTPException, Request
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def login_user(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["role"] = user.role.name
    request.session["username"] = user.username


def logout_user(request: Request) -> None:
    request.session.clear()


def require_role(request: Request, roles: list[str]) -> None:
    role = request.session.get("role")
    if role not in roles:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
