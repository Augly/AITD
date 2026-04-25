from backend.engine.models import KLineCache

class SyncWorker:
    def __init__(self, session_factory, interval_minutes=5):
        self.Session = session_factory
        self.interval_minutes = interval_minutes

    def run_incremental_sync(self):
        # Stub for the actual 5-minute loop
        pass

    def sync_klines(self, symbol: str, interval: str, klines: list):
        with self.Session() as session:
            for k in klines:
                # Upsert or insert (simplified as insert for minimal)
                cache = KLineCache(
                    symbol=symbol,
                    interval=interval,
                    timestamp=k["timestamp"],
                    open=k["open"],
                    high=k["high"],
                    low=k["low"],
                    close=k["close"],
                    volume=k["volume"]
                )
                session.add(cache)
            session.commit()
