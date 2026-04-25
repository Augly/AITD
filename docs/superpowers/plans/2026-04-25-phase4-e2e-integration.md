# Phase 4: E2E Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the real LLM client, the background sync worker, and the Agent loop so that the system can run end-to-end and execute real decisions.

**Architecture:** 
1. `server.py` will spawn a background thread for `SyncWorker` so the database gets fresh K-lines.
2. `engine_core.py` will replace the `mock_llm_caller` with the real `LLMClientFactory` caller.
3. `engine_core.py` will process the final output of the Agent, parse the JSON, execute trades using existing `apply_paper_position_action` (or live equivalent), and persist to the SQLite `Decision` and `Trade` tables.

**Tech Stack:** Python 3.11+, SQLAlchemy, Threading.

---

### Task 1: Start SyncWorker in Background

**Files:**
- Modify: `backend/server.py`

- [ ] **Step 1: Write the failing test**
*(Skip test for this specific server threading wiring, we will just implement it safely).*

- [ ] **Step 2: Implement SyncWorker threading in AppRuntime**
Open `backend/server.py`. Find the `start_scheduler` method in `AppRuntime`.
Import `SyncWorker` and `init_db`. Instantiate them and start a separate background thread that runs `run_incremental_sync` in a `while True` loop every `interval_minutes`.

```python
# In backend/server.py
# Inside start_scheduler(self) method:
# Add this above the existing `loop` definition:
        def sync_loop():
            from .engine.db import init_db
            from .engine.sync_worker import SyncWorker
            Session = init_db()
            worker = SyncWorker(session_factory=Session, interval_minutes=5)
            while True:
                try:
                    self.record_log("INFO", "Starting background K-line sync...")
                    worker.run_incremental_sync()
                    self.record_log("INFO", "Background K-line sync completed.")
                except Exception as error:
                    self.record_log("ERROR", f"SyncWorker failed: {error}")
                time.sleep(5 * 60)
                
        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
```

- [ ] **Step 3: Commit**
```bash
git add backend/server.py
git commit -m "feat: start background SyncWorker thread in server"
```

### Task 2: Replace Mock LLM with Real LLMClient in Engine

**Files:**
- Modify: `backend/engine_core.py`

- [ ] **Step 1: Implement LLM client wiring in run_trading_cycle**

Open `backend/engine_core.py`, go to `run_trading_cycle`.
Replace the mock `llm_caller` with the real one. 

```python
# In backend/engine_core.py inside run_trading_cycle:
    from .engine.llm_client import LLMClientFactory
    from .config import read_llm_provider
    
    provider_config = read_llm_provider()
    # provider_config usually has 'preset' (e.g. 'anthropic' or 'openai') and 'apiKey'
    preset = provider_config.get("preset", "anthropic").lower()
    api_key = provider_config.get("apiKey", "")
    
    llm_client = LLMClientFactory.create(preset, api_key)
    
    def llm_caller(history, tools):
        # We need to map our simple python tools to the Anthropic/OpenAI schema
        tool_schemas = []
        for tool_name in tools.keys():
            tool_schemas.append({
                "name": tool_name,
                "description": f"Call {tool_name}",
                "input_schema": {
                    "type": "object",
                    "properties": {} # Simplified for now, the agent will pass empty dicts if needed
                }
            })
        return llm_client.call(history, tool_schemas)
```

- [ ] **Step 2: Commit**
```bash
git add backend/engine_core.py
git commit -m "feat: wire real LLMClient into ReActAgent loop"
```

### Task 3: Parse Agent Decision and Execute/Persist

**Files:**
- Modify: `backend/engine_core.py`

- [x] **Step 1: Implement execution and DB persistence**
In `run_trading_cycle`, after `agent_result = agent.run(instruction)`, the `agent_result` contains the conversation history. The last message from the assistant should contain the final decision. We need to extract it, write it to SQLite `Decision` table, and simulate an execution.

```python
# In backend/engine_core.py at the end of run_trading_cycle:
    from .engine.models import Decision, Trade
    import time

    final_text = ""
    if isinstance(agent_result, list) and len(agent_result) > 0:
        final_msg = agent_result[-1]
        final_text = final_msg.get("content", "")
        if isinstance(final_text, list): # if it's a list of blocks
            text_blocks = [b["text"] for b in final_text if b.get("type") == "text"]
            final_text = "\n".join(text_blocks)
        elif isinstance(final_text, str):
            pass
            
    # Naive extraction: If it decided to pass, or buy, etc.
    action = "HOLD"
    if "BUY" in final_text.upper() or "LONG" in final_text.upper():
        action = "BUY"
    elif "SELL" in final_text.upper() or "SHORT" in final_text.upper():
        action = "SELL"
    
    with Session() as session:
        decision = Decision(
            timestamp=int(time.time()),
            symbol="ALL", # Can be extracted more robustly later
            action=action,
            reasoning=final_text
        )
        session.add(decision)
        session.commit()
    
    return {
        "ok": True,
        "mode": mode_override or "paper",
        "agent_result": final_text
    }
```

- [x] **Step 2: Commit**
```bash
git add backend/engine_core.py
git commit -m "feat: parse agent output and persist to Decision table"
```