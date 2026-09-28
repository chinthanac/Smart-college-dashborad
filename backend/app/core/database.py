from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


if settings.database_url.startswith("postgresql"):
    engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)
else:
    # StaticPool shares ONE connection across every worker thread, so
    # concurrent requests trample each other's cursors and surface as
    # spurious 401s. A file-backed database gets a real pool instead;
    # StaticPool is only correct for in-memory SQLite.
    is_memory_db = ":memory:" in settings.database_url
    engine = create_engine(
        settings.database_url,
        echo=False,
        connect_args={"check_same_thread": False},
        **({"poolclass": StaticPool} if is_memory_db else {}),
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_and_tables():
    from app.core.security import get_password_hash
    from app.models.user import User
    from app.services import time_slot_service

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@smartcollege.com").first()
        if admin is None:
            admin = User(
                name="System Administrator",
                email="admin@smartcollege.com",
                password_hash=get_password_hash("Chaadmin123@"),
                role="ADMIN",
                is_active=True,
            )
            db.add(admin)

        admin.name = admin.name or "System Administrator"
        admin.role = "ADMIN"
        admin.is_active = True
        admin.password_hash = get_password_hash("Chaadmin123@")
        db.commit()

        # A fresh install needs a working day before anything can be
        # scheduled against it. Skipped entirely once any period exists.
        time_slot_service.seed_default_slots(db)
    finally:
        db.close()
