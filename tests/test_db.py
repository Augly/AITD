import pytest
from sqlalchemy import create_engine, inspect
from backend.engine.models import Base
from backend.engine.db import init_db

def test_db_initialization():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    inspector = inspect(engine)
    assert inspector.has_table("kline_cache")
    assert inspector.has_table("agent_memory")
