import pytest
from backend.engine.sync_worker import SyncWorker
from backend.engine.models import KLineCache
from sqlalchemy import create_engine
from backend.engine.db import init_db

def test_sync_worker_adds_klines():
    engine = create_engine("sqlite:///:memory:")
    Session = init_db(engine)
    worker = SyncWorker(session_factory=Session)
    worker.sync_klines("BTCUSDT", "15m", [{"timestamp": 123, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}])
    
    with Session() as session:
        kline = session.query(KLineCache).first()
        assert kline.symbol == "BTCUSDT"
        assert kline.close == 2.0
