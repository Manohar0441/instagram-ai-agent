from app.database.base import Base
from app.database.session import engine

# Import models so SQLAlchemy registers them
from app.models import User


def init_db():
    Base.metadata.create_all(bind=engine)