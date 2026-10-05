import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db
from app.models import Base
from app.seed import seed_catalog


@pytest.fixture
def Session(monkeypatch):
    """База в памяти с демо-каталогом; бот и тесты работают с ней одной."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "SessionLocal", factory)
    with factory() as s:
        seed_catalog(s)
        s.commit()
    return factory


@pytest.fixture
def s(Session):
    with Session() as session:
        yield session
        session.commit()
