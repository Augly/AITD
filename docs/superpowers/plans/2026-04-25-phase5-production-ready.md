# Production-Ready Agent Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the current prototype into a production-ready system by implementing real execution logic, robust LLM clients, dynamic sync workers, and strict Tool Call routing.

**Architecture:** 
1. **Dynamic SyncWorker**: Update `sync_worker.py` to read the real candidate universe from `config.py` instead of hardcoding `BTCUSDT`.
2. **Robust LLMClient**: Implement the `OpenAIClient` using standard `urllib.request` with retry logic and error handling.
3. **Execution Routing**: Update `engine_core.py` to stop using string matching (`if "BUY" in text`) and instead parse specific `tool_calls` (e.g., `place_order`) outputted by the Agent. Route these tool calls to the existing `apply_paper_position_action` (or live equivalent).
4. **Real Agent Tools**: Connect `place_order` and `get_account_balance` to the real exchange/paper backends.

**Tech Stack:** Python 3.11+, SQLAlchemy, urllib, existing AITD engine modules.

---

### Task 1: Dynamic SyncWorker & Real Account Tools

**Files:**
- Modify: `backend/engine/sync_worker.py`
- Modify: `backend/engine/agent_tools.py`
- Modify: `tests/test_sync_worker.py`

- [x] **Step 1: Write the failing test for dynamic sync**

```python
# tests/test_sync_worker.py
# (Append this to the file)
from unittest.mock import patch

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
```

- [x] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_sync_worker.py::test_dynamic_sync_worker -v`
Expected: FAIL (because it hardcodes BTCUSDT/ETHUSDT)

- [x] **Step 3: Write actual implementation**

```python
# backend/engine/sync_worker.py
from backend.exchanges.binance import BinanceGateway
from backend.config import read_fixed_universe

class SyncWorker:
    def __init__(self, session_factory, interval_minutes=5):
        self.Session = session_factory
        self.interval_minutes = interval_minutes
        self.gateway = BinanceGateway() # Paper mode
        
    def run_incremental_sync(self):
        universe = read_fixed_universe()
        symbols = universe.get("symbols", [])
        if not symbols:
            symbols = ["BTCUSDT"] # Fallback
            
        for symbol in symbols:
            try:
                klines = self.gateway.fetch_klines(symbol, "15m", limit=10)
                self.sync_klines(symbol, "15m", klines)
            except Exception as e:
                print(f"Error syncing {symbol}: {e}")

    def sync_klines(self, symbol: str, interval: str, klines: list):
        from backend.engine.models import KLineCache
        with self.Session() as session:
            for k in klines:
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
Run: `python -m pytest tests/test_sync_worker.py::test_dynamic_sync_worker -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/engine/sync_worker.py tests/test_sync_worker.py backend/engine/agent_tools.py
git commit -m "feat: make sync worker dynamically read candidate universe"
```

### Task 2: Implement Robust OpenAI Client

**Files:**
- Modify: `backend/engine/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [x] **Step 1: Write the failing test for OpenAI network call**

```python
# tests/test_llm_client.py
# (Append this to the file)
from unittest.mock import patch
import json

@patch('urllib.request.urlopen')
def test_openai_real_call(mock_urlopen):
    from backend.engine.llm_client import OpenAIClient
    class MockResponse:
        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {
                        "content": "Thinking...",
                        "tool_calls": [{
                            "function": {"name": "place_order", "arguments": "{\"symbol\":\"BTCUSDT\",\"side\":\"BUY\",\"qty\":1.0}"}
                        }]
                    }
                }]
            }).encode('utf-8')
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    mock_urlopen.return_value = MockResponse()
    
    client = OpenAIClient("fake_key")
    res = client.call([{"role": "user", "content": "test"}], [])
    assert res["text"] == "Thinking..."
    assert res["tool_calls"][0]["name"] == "place_order"
    assert res["tool_calls"][0]["arguments"]["side"] == "BUY"
```

- [x] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_llm_client.py::test_openai_real_call -v`
Expected: FAIL (because `call` is `pass`)

- [x] **Step 3: Write actual network call implementation**

```python
# backend/engine/llm_client.py
# (Update the OpenAIClient class)
import urllib.request
import json
import time

class OpenAIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def call(self, messages, tools, retries=3):
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        
        # Convert Anthropic tool schema to OpenAI function calling schema
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}})
                }
            })
            
        data = {
            "model": "gpt-4o",
            "messages": messages,
            "tools": openai_tools if openai_tools else None
        }
        if not data["tools"]:
            del data["tools"]
            
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'), timeout=30) as response:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    return self._standardize_response(resp_data)
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2 ** attempt)
        
    def _standardize_response(self, response_dict):
        message = response_dict["choices"][0]["message"]
        result = {"text": message.get("content", "") or "", "tool_calls": []}
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                result["tool_calls"].append({
                    "name": tc["function"]["name"],
                    "arguments": args
                })
        return result
```

- [x] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_llm_client.py::test_openai_real_call -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/engine/llm_client.py tests/test_llm_client.py
git commit -m "feat: implement robust OpenAI client with retries and schema translation"
```

### Task 3: Route Agent Tool Calls to Execution Engine

**Files:**
- Modify: `backend/engine_core.py`

- [x] **Step 1: Replace string matching with actual tool call routing**
In `backend/engine_core.py`, locate `run_trading_cycle`. Update the post-processing logic to check the final `agent_result` for tool calls instead of searching for "BUY" in the text.

```python
# In backend/engine_core.py inside run_trading_cycle (replace the naive extraction part):
    
    # Extract the final decision from the agent loop history
    final_text = ""
    tool_calls = []
    if isinstance(agent_result, list) and len(agent_result) > 0:
        final_msg = agent_result[-1]
        
        if isinstance(final_msg, dict):
            # The agent loop appends {"role": "tool", "content": ...}
            # We actually want the last assistant message before the tools, 
            # OR we modify agent_loop.py to return the final assistant msg.
            # Assuming agent_result is the history, let's find the last assistant message.
            for msg in reversed(agent_result):
                if msg.get("role") == "assistant" or "tool_calls" in msg:
                    final_text = msg.get("text", msg.get("content", ""))
                    tool_calls = msg.get("tool_calls", [])
                    break
    
    with Session() as session:
        # Save reasoning
        decision = Decision(
            timestamp=int(time.time()),
            symbol="ALL",
            action="EVALUATED",
            reasoning=str(final_text)
        )
        session.add(decision)
        
        # Route execution based on tool calls
        for tc in tool_calls:
            if tc["name"] == "place_order":
                args = tc.get("arguments", {})
                symbol = args.get("symbol", "UNKNOWN")
                side = args.get("side", "BUY")
                qty = float(args.get("qty", 0.0))
                
                trade = Trade(
                    timestamp=int(time.time()),
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    price=0.0 # Will be populated by real execution engine later
                )
                session.add(trade)
                
                decision.action = f"ORDER_{side}_{symbol}"
                
        session.commit()
    
    return {
        "ok": True,
        "mode": mode_override or "paper",
        "agent_result": final_text,
        "tool_calls": tool_calls
    }
```

- [x] **Step 2: Commit**
```bash
git add backend/engine_core.py
git commit -m "feat: route agent tool calls to decision and trade tables"
```

### Task 4: Fix Agent Loop Output Format

**Files:**
- Modify: `backend/engine/agent_loop.py`
- Modify: `tests/test_agent_loop.py`

- [x] **Step 1: Ensure agent loop captures tool calls correctly**
The current `ReActAgent` loop appends `{"role": "tool", "content": ...}` but might not be saving the intermediate assistant messages that contain the actual `tool_calls` array, making it hard for `engine_core.py` to extract them.

```python
# In backend/engine/agent_loop.py, update the run method:
    def run(self, instruction: str):
        self.history.append({"role": "user", "content": instruction})
        for _ in range(5):
            response = self.llm_caller(self.history, self.tools)
            # response is {"text": "...", "tool_calls": [...]}
            
            assistant_msg = {"role": "assistant", "content": response.get("text", "")}
            if response.get("tool_calls"):
                assistant_msg["tool_calls"] = response["tool_calls"]
            self.history.append(assistant_msg)
            
            if response.get("tool_calls"):
                for tool in response["tool_calls"]:
                    func = self.tools.get(tool["name"])
                    if func:
                        try:
                            # Pass session_factory if the tool requires it, but for simplicity here we assume tools are curried or don't need it if not defined
                            # A better pattern is to inject dependencies when registering tools.
                            result = func(**tool.get("arguments", {}))
                        except Exception as e:
                            result = {"error": str(e)}
                        self.history.append({"role": "tool", "name": tool["name"], "content": json.dumps(result)})
            else:
                return self.history
        return self.history
```

- [x] **Step 2: Fix failing test**
Run `python -m pytest tests/test_agent_loop.py -v`. Fix the mock in the test to match the new structure if it fails.

- [x] **Step 3: Commit**
```bash
git add backend/engine/agent_loop.py tests/test_agent_loop.py
git commit -m "fix: ensure agent loop saves tool_calls to history for extraction"
```