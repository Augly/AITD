from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

def init_db(engine=None):
    if engine is None:
        engine = create_engine("sqlite:///data/aitd.sqlite3")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
