from app.database.base import Base
from app.database.session import engine

# Import all models here so SQLAlchemy registers them
from app.models.user import User


def init_db():
    Base.metadata.create_all(bind=engine)