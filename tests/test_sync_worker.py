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

def test_sync_worker_incremental():
    from backend.engine.sync_worker import SyncWorker
    worker = SyncWorker(session_factory=None)
    # Testing that it correctly sets up a 5 min interval schedule stub
    assert worker.interval_minutes == 5

from unittest.mock import patch

def test_sync_worker_real_fetch():
    from backend.engine.sync_worker import SyncWorker
    from backend.engine.db import init_db
    from sqlalchemy import create_engine
    
    engine = create_engine("sqlite:///:memory:")
    Session = init_db(engine)
    worker = SyncWorker(session_factory=Session)
    
    with patch('backend.exchanges.binance.BinanceGateway.fetch_klines') as mock_fetch:
        mock_fetch.return_value = [{"timestamp": 1, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}]
        worker.run_incremental_sync()
        
    with Session() as session:
        from backend.engine.models import KLineCache
        assert session.query(KLineCache).count() > 0

@patch('backend.engine.sync_worker.read_fixed_universe')
@patch('backend.exchanges.binance.BinanceGateway.fetch_klines')
def test_dynamic_sync_worker(mock_fetch, mock_universe):
    from backend.engine.sync_worker import SyncWorker
    from backend.engine.db import init_db
    from sqlalchemy import create_engine
    
    mock_universe.return_value = {"symbols": ["XRPUSDT"]}
    mock_fetch.return_value = [{"timestamp": 1, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}]
    
    engine = create_engine("sqlite:///:memory:")
    Session = init_db(engine)
    worker = SyncWorker(session_factory=Session)
    worker.run_incremental_sync()
    
    with Session() as session:
        from backend.engine.models import KLineCache
        kline = session.query(KLineCache).first()
        assert kline is not None
        assert kline.symbol == "XRPUSDT"

