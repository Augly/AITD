import pytest
from backend.engine.agent_tools import get_kline_data, get_account_balance, list_universe, get_position, get_recent_decisions, place_order, close_position, pass_turn
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

def test_new_tools():
    assert list_universe() == ["BTCUSDT", "ETHUSDT"]
    assert get_position("BTCUSDT") == {"symbol": "BTCUSDT", "qty": 0}
    assert get_recent_decisions(5) == []
    assert place_order("BTCUSDT", "buy", 1.0) == {"status": "success", "symbol": "BTCUSDT"}
    assert close_position("BTCUSDT") == {"status": "closed", "symbol": "BTCUSDT"}
    assert pass_turn() == {"status": "passed"}
