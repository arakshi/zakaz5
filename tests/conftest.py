import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_bloom.db"
os.environ["SECRET_KEY"] = "test"

from app.main_factory import create_app  # noqa: E402
from app.db.session import Base, engine, SessionLocal  # noqa: E402
from seed_demo import main as seed_main  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_main()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()
