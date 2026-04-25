# AI Agent Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the monolithic AITD system into an autonomous LLM-driven trading agent backed by a SQLite database and an event-driven background sync worker.

**Architecture:** We will replace the JSON-based state with SQLAlchemy models. A decoupled background worker will sync market data to the database and emit price anomaly events. The core engine will be replaced with a custom ReAct (Reasoning + Acting) loop that calls tools (Market, Account, Memory) and logs execution to the database.

**Tech Stack:** Python 3.11+, SQLAlchemy, SQLite, Pydantic, threading.

---

### Task 1: Setup SQLAlchemy Database and Models

**Files:**
- Create: `backend/engine/db.py`
- Create: `backend/engine/models.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test for DB initialization**

```python
# tests/test_db.py
import pytest
from sqlalchemy import create_engine
from backend.engine.models import Base
from backend.engine.db import init_db

def test_db_initialization():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    assert engine.has_table("kline_cache")
    assert engine.has_table("agent_memory")
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Write minimal implementation for models and db**

```python
# backend/engine/models.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, JSON

Base = declarative_base()

class KLineCache(Base):
    __tablename__ = 'kline_cache'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    interval = Column(String)
    timestamp = Column(Integer, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class AgentMemory(Base):
    __tablename__ = 'agent_memory'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(Integer)
    reasoning = Column(String)
    decision = Column(JSON)

# backend/engine/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

def init_db(engine=None):
    if engine is None:
        engine = create_engine("sqlite:///data/aitd.sqlite3")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/test_db.py backend/engine/db.py backend/engine/models.py
git commit -m "feat: add sqlalchemy models for agent architecture"
```

### Task 2: Implement Background Sync Worker

**Files:**
- Create: `backend/engine/sync_worker.py`
- Test: `tests/test_sync_worker.py`

- [x] **Step 1: Write the failing test for the sync worker**

```python
# tests/test_sync_worker.py
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
```

- [x] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_sync_worker.py -v`
Expected: FAIL

- [x] **Step 3: Write minimal implementation**

```python
# backend/engine/sync_worker.py
from backend.engine.models import KLineCache

class SyncWorker:
    def __init__(self, session_factory):
        self.Session = session_factory

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
```

- [x] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_sync_worker.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add tests/test_sync_worker.py backend/engine/sync_worker.py
git commit -m "feat: implement background sync worker for klines"
```

### Task 3: Implement Agent Tools

**Files:**
- Create: `backend/engine/agent_tools.py`
- Test: `tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test for agent tools**

```python
# tests/test_agent_tools.py
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
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_agent_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# backend/engine/agent_tools.py
from backend.engine.models import KLineCache

def get_kline_data(symbol: str, interval: str, session_factory):
    with session_factory() as session:
        klines = session.query(KLineCache).filter_by(symbol=symbol, interval=interval).order_by(KLineCache.timestamp.desc()).limit(100).all()
        return [{"timestamp": k.timestamp, "close": k.close} for k in reversed(klines)]

def get_account_balance():
    # Stub for account balance tool
    return {"USDT": 10000}
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/test_agent_tools.py backend/engine/agent_tools.py
git commit -m "feat: implement agent tools for ReAct loop"
```

### Task 4: Implement Custom ReAct Agent Loop

**Files:**
- Create: `backend/engine/agent_loop.py`
- Test: `tests/test_agent_loop.py`

- [x] **Step 1: Write the failing test**

```python
# tests/test_agent_loop.py
from backend.engine.agent_loop import ReActAgent

def mock_llm_call(prompt, tools):
    # Simulate LLM choosing a tool
    return {"tool_calls": [{"name": "get_account_balance", "arguments": {}}]}

def test_agent_tool_calling_loop():
    agent = ReActAgent(llm_caller=mock_llm_call)
    response = agent.run("Check my balance")
    assert "USDT" in str(response)
```

- [x] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_agent_loop.py -v`
Expected: FAIL

- [x] **Step 3: Write minimal implementation**

```python
# backend/engine/agent_loop.py
import json
from backend.engine.agent_tools import get_account_balance

class ReActAgent:
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
        self.tools = {
            "get_account_balance": get_account_balance
        }
        self.history = []

    def run(self, instruction: str):
        self.history.append({"role": "user", "content": instruction})
        for _ in range(5): # Max iterations
            response = self.llm_caller(self.history, self.tools)
            if "tool_calls" in response:
                for tool in response["tool_calls"]:
                    func = self.tools.get(tool["name"])
                    if func:
                        result = func(**tool.get("arguments", {}))
                        self.history.append({"role": "tool", "content": json.dumps(result)})
            else:
                return response
        return self.history
```

- [x] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_agent_loop.py -v`
Expected: PASS (if mock is adjusted to break loop)

- [x] **Step 5: Commit**
```bash
git add tests/test_agent_loop.py backend/engine/agent_loop.py
git commit -m "feat: implement custom ReAct agent loop"
```

### Task 5: Integrate Event Trigger & Agent Loop into Engine

**Files:**
- Modify: `backend/engine/engine_core.py` (assuming refactored from `engine.py`)

- [x] **Step 1: Setup integration logic**
Replace the static `run_trading_cycle` with a function that instantiates `ReActAgent`, loads `AgentMemory` from SQLite, and starts the reasoning loop based on a trigger event (Timer or Anomaly).

- [x] **Step 2: Commit**
```bash
git commit -am "feat: integrate ReAct loop and event triggers into engine core"
```