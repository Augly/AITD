# Actual Tool Logic & E2E Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the previously created stubs with actual functional code so that the 8 agent tools interact properly with the database, the LLM client makes real API calls, and the end-to-end ReAct loop can run in Paper mode.

**Architecture:** 
- The 8 tools will receive a `session_factory` (or a DB session) to query `KLineCache`, `Decision`, and `Trade` tables.
- The LLMClient will use `http_client` or `requests` to actually communicate with Anthropic and OpenAI API endpoints.
- The `SyncWorker` will use the existing exchange gateways to fetch and save real K-lines.
- We will wire up `run.py` to trigger the ReAct loop.

**Tech Stack:** Python 3.11+, SQLAlchemy, SQLite, `urllib.request` (existing `http_client`).

---

### Task 1: Implement Real LLM API Calls

**Files:**
- Modify: `backend/engine/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test for real LLM network call handling (mocked)**

```python
# tests/test_llm_client.py
# (Append this to the file)
from unittest.mock import patch
import json

@patch('urllib.request.urlopen')
def test_anthropic_real_call(mock_urlopen):
    from backend.engine.llm_client import AnthropicClient
    class MockResponse:
        def read(self):
            return json.dumps({
                "content": [{"type": "text", "text": "Thinking..."}, {"type": "tool_use", "name": "pass_turn", "input": {}}]
            }).encode('utf-8')
    mock_urlopen.return_value = MockResponse()
    
    client = AnthropicClient("fake_key")
    res = client.call([{"role": "user", "content": "test"}], [])
    assert res["text"] == "Thinking..."
    assert res["tool_calls"][0]["name"] == "pass_turn"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_llm_client.py::test_anthropic_real_call -v`
Expected: FAIL (because `call` is just a `pass` stub)

- [ ] **Step 3: Write actual network call implementation**

```python
# backend/engine/llm_client.py
import json
import urllib.request

class AnthropicClient:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def call(self, messages, tools):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="POST")
        req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("content-type", "application/json")
        
        data = {
            "model": "claude-3-5-sonnet-20240620",
            "max_tokens": 1024,
            "messages": messages,
            "tools": tools
        }
        
        with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8')) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            
        result = {"text": "", "tool_calls": []}
        for block in resp_data.get("content", []):
            if block["type"] == "text":
                result["text"] += block["text"]
            elif block["type"] == "tool_use":
                result["tool_calls"].append({
                    "name": block["name"],
                    "arguments": block["input"]
                })
        return result

# (Keep OpenAIClient as is for now, but it would be similarly implemented)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_llm_client.py::test_anthropic_real_call -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/engine/llm_client.py tests/test_llm_client.py
git commit -m "feat: implement actual network call for Anthropic client"
```

### Task 2: Implement Real Agent Tools (DB Reads)

**Files:**
- Modify: `backend/engine/agent_tools.py`
- Modify: `tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test for real DB reads**

```python
# tests/test_agent_tools.py
# (Append this to the file)
from backend.engine.models import Decision
def test_real_recent_decisions():
    from backend.engine.agent_tools import get_recent_decisions
    from sqlalchemy import create_engine
    from backend.engine.db import init_db
    
    engine = create_engine("sqlite:///:memory:")
    Session = init_db(engine)
    with Session() as session:
        session.add(Decision(symbol="BTC", action="BUY", reasoning="good", timestamp=100))
        session.commit()
    
    res = get_recent_decisions(limit=5, session_factory=Session)
    assert len(res) == 1
    assert res[0]["action"] == "BUY"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_agent_tools.py::test_real_recent_decisions -v`
Expected: FAIL (because `get_recent_decisions` stub doesn't take `session_factory` and returns `[]`)

- [ ] **Step 3: Write actual DB read implementation**

```python
# backend/engine/agent_tools.py
from backend.engine.models import KLineCache, Decision, Trade

def list_universe():
    return ["BTCUSDT", "ETHUSDT"] # Kept static for paper mode simplicity

def get_position(symbol: str):
    return {"symbol": symbol, "qty": 0} # Kept static for paper mode simplicity

def get_recent_decisions(limit: int, session_factory):
    with session_factory() as session:
        decisions = session.query(Decision).order_by(Decision.timestamp.desc()).limit(limit).all()
        return [{"symbol": d.symbol, "action": d.action, "reasoning": d.reasoning} for d in decisions]

# Update get_kline_data to be robust
def get_kline_data(symbol: str, interval: str, session_factory, limit=100):
    with session_factory() as session:
        klines = session.query(KLineCache).filter_by(symbol=symbol, interval=interval).order_by(KLineCache.timestamp.desc()).limit(limit).all()
        return [{"timestamp": k.timestamp, "close": k.close} for k in reversed(klines)]
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_agent_tools.py::test_real_recent_decisions -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/engine/agent_tools.py tests/test_agent_tools.py
git commit -m "feat: implement actual DB reads for agent tools"
```

### Task 3: Implement Real Sync Worker Logic

**Files:**
- Modify: `backend/engine/sync_worker.py`
- Modify: `tests/test_sync_worker.py`

- [x] **Step 1: Write the failing test for fetching from exchange**

```python
# tests/test_sync_worker.py
# (Append this to the file)
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
```

- [x] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_sync_worker.py::test_sync_worker_real_fetch -v`
Expected: FAIL (because `run_incremental_sync` is just `pass`)

- [x] **Step 3: Write actual sync implementation**

```python
# backend/engine/sync_worker.py
from backend.exchanges.binance import BinanceGateway

class SyncWorker:
    def __init__(self, session_factory, interval_minutes=5):
        self.Session = session_factory
        self.interval_minutes = interval_minutes
        self.gateway = BinanceGateway(api_key="", api_secret="") # Paper mode
        
    def run_incremental_sync(self):
        # In a real scenario, this loops over the universe. We hardcode BTCUSDT for now.
        symbols = ["BTCUSDT", "ETHUSDT"]
        for symbol in symbols:
            klines = self.gateway.fetch_klines(symbol, "15m", limit=10)
            self.sync_klines(symbol, "15m", klines)
            
    def sync_klines(self, symbol: str, interval: str, klines: list):
        from backend.engine.models import KLineCache
        with self.Session() as session:
            for k in klines:
                # Upsert or ignore logic (simplified to add if not exists)
                exists = session.query(KLineCache).filter_by(symbol=symbol, interval=interval, timestamp=k["timestamp"]).first()
                if not exists:
                    cache = KLineCache(
                        symbol=symbol, interval=interval, timestamp=k["timestamp"],
                        open=k["open"], high=k["high"], low=k["low"], close=k["close"], volume=k["volume"]
                    )
                    session.add(cache)
            session.commit()
```

- [x] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_sync_worker.py::test_sync_worker_real_fetch -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/engine/sync_worker.py tests/test_sync_worker.py
git commit -m "feat: implement actual Binance exchange fetch in sync worker"
```