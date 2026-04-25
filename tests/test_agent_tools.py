import pytest
from backend.engine.agent_tools import get_kline_data, get_account_balance
from sqlalchemy import create_engine
from backend.engine.db import init_db
from backend.engine.models import KLineCache

def test_get_kline_data():
    engine = create_engine("sqlite:///:memory:")
    Session = init_db(engine)
    with Session() as session:
        session.add(KLineCache(symbol="ETHUSDT", interval="15m", timestamp=1000, close=3000))
        session.commit()
    
    data = get_kline_data("ETHUSDT", "15m", session_factory=Session)
    assert len(data) == 1
    assert data[0]["close"] == 3000
