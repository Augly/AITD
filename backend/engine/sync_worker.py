from backend.engine.models import KLineCache
from backend.exchanges.binance import BinanceGateway
from backend.config import read_fixed_universe
import logging

logger = logging.getLogger(__name__)

class SyncWorker:
    def __init__(self, session_factory, interval_minutes=5):
        self.Session = session_factory
        self.interval_minutes = interval_minutes
        self.gateway = BinanceGateway() # Paper mode
        
    def cleanup_old_klines(self):
        """Removes klines older than 30 days to prevent SQLite bloat."""
        import time
        from backend.engine.models import KLineCache
        thirty_days_ago = int(time.time() * 1000) - (30 * 24 * 60 * 60 * 1000)
        
        with self.Session() as session:
            try:
                deleted = session.query(KLineCache).filter(KLineCache.timestamp < thirty_days_ago).delete()
                session.commit()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old klines from cache.")
            except Exception as e:
                session.rollback()
                logger.error(f"Error cleaning up old klines: {e}")

    def run_incremental_sync(self):
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        universe = read_fixed_universe()
        symbols = universe.get("symbols", [])
        if not symbols:
            symbols = ["BTCUSDT"] # Fallback
            
        def sync_single_symbol(symbol):
            try:
                # Add simple exponential backoff for rate limits/timeouts
                for attempt in range(3):
                    try:
                        klines = self.gateway.fetch_klines(symbol, "15m", limit=10)
                        self.sync_klines(symbol, "15m", klines)
                        break
                    except Exception as inner_e:
                        err_str = str(inner_e).lower()
                        if ("timeout" in err_str or "connection reset" in err_str or "network error" in err_str) and attempt < 2:
                            time.sleep(2 ** attempt)
                            continue
                        raise inner_e
            except Exception as e:
                # Don't clutter logs with expected timeout errors or Binance region restrictions
                err_str = str(e).lower()
                if "timed out" not in err_str and "timeout" not in err_str and "451" not in err_str and "restricted location" not in err_str and "connection reset" not in err_str and "network error" not in err_str:
                    logger.error(f"Error syncing {symbol}: {e}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(sync_single_symbol, sym) for sym in symbols]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    pass
                
        # Perform cleanup
        self.cleanup_old_klines()

    def sync_klines(self, symbol: str, interval: str, klines: list):
        if not klines:
            return
        from backend.engine.models import KLineCache
        with self.Session() as session:
            try:
                # Bulk query existing timestamps to avoid N+1 queries
                # Handle dictionary vs object format depending on how klines were parsed
                timestamps = [k.get("timestamp") or k.get("openTime") for k in klines if (k.get("timestamp") or k.get("openTime")) is not None]
                if not timestamps:
                    return
                    
                existing = session.query(KLineCache.timestamp).filter(
                    KLineCache.symbol == symbol,
                    KLineCache.interval == interval,
                    KLineCache.timestamp.in_(timestamps)
                ).all()
                existing_ts = {t[0] for t in existing}
                
                new_caches = []
                for k in klines:
                    ts = k.get("timestamp") or k.get("openTime")
                    if ts and ts not in existing_ts:
                        new_caches.append(KLineCache(
                            symbol=symbol, interval=interval, timestamp=ts,
                            open=k["open"], high=k["high"], low=k["low"], close=k["close"], volume=k["volume"]
                        ))
                
                if new_caches:
                    try:
                        # Try standard bulk save first for generic DB support
                        session.bulk_save_objects(new_caches)
                        session.commit()
                    except Exception:
                        session.rollback()
                        # Fallback to single inserts if bulk fails (ignore duplicates)
                        for c in new_caches:
                            try:
                                session.add(c)
                                session.commit()
                            except Exception:
                                session.rollback()
            except Exception as e:
                session.rollback()
                logger.error(f"DB Error syncing klines for {symbol}: {e}")

