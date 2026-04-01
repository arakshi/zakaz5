from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import Base, SessionLocal, engine
from app.routers import admin, auth, shop
from app.services.bootstrap_service import ensure_initial_data


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        ensure_initial_data(db)

    Path("uploads").mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    app.include_router(shop.router)
    app.include_router(auth.router)
    app.include_router(admin.router)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, _exc):
        return RedirectResponse("/404")

    @app.get("/404")
    async def not_found_page():
        return {"detail": "Страница не найдена"}

    return app
