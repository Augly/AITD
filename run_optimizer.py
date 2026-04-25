import sys
import time
from backend.engine.db import init_db
from backend.engine.models import KLineCache
from backend.engine.optimizer import optimize_brain_loop

def fetch_recent_klines():
    Session = init_db()
    with Session() as session:
        # Fetch up to 1000 recent klines for backtesting
        klines = session.query(KLineCache).filter_by(symbol="BTCUSDT", interval="15m").order_by(KLineCache.timestamp.asc()).limit(1000).all()
        return [{"timestamp": k.timestamp, "close": k.close, "high": k.high, "low": k.low, "volume": k.volume} for k in klines]

def main():
    print("Loading historical data for optimization...")
    klines = fetch_recent_klines()
    if len(klines) < 100:
        print("Not enough historical data in SQLite to run optimization. Please let the SyncWorker run for a while.")
        # For demonstration, we can mock some klines
        print("Mocking historical data for demonstration purposes...")
        klines = []
        base_price = 50000
        for i in range(1000):
            import random
            base_price += random.uniform(-100, 100)
            klines.append({
                "timestamp": int(time.time()) - (1000 - i) * 900,
                "close": base_price,
                "high": base_price + 50,
                "low": base_price - 50,
                "volume": random.uniform(10, 100)
            })
            
    print(f"Loaded {len(klines)} K-lines.")
    
    # We run 100 iterations as requested
    optimize_brain_loop(klines, iterations=100)

if __name__ == "__main__":
    main()
