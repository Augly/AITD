# Phase 6 Final Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the ReAct Agent output to the real ExecutionBackend and refine the prompt to truly enable tool-driven autonomous trading.

**Architecture:** We will replace the dummy execution logic in `engine_core.py` with actual instantiation and calls to `PaperBackend`/`LiveBackend` from `executor.py`. We will also overhaul the `build_prompt` function to provide a lean context snapshot, forcing the LLM to use its tools for data discovery.

**Tech Stack:** Python 3.11+, AITD engine modules.

---

### Task 1: Connect Agent to Execution Backend

**Files:**
- Modify: `backend/engine_core.py`

- [x] **Step 1: Write the failing test**
*(Skipping test as this is a high-level integration wiring task)*

- [x] **Step 2: Update `run_trading_cycle` to use `executor.py`**
In `backend/engine_core.py`, locate the `run_trading_cycle` function. Find the section where we parse `tool_calls` and write to the `Trade` table. Replace it with a call to the actual `ExecutionBackend`.

```python
# In backend/engine_core.py inside run_trading_cycle:
    # After saving the decision...
    
    from .engine.executor import PaperBackend, LiveBackend
    from .config import read_account_configs
    
    # Initialize the proper backend
    accounts = read_account_configs()
    account_config = accounts.get(mode_override or "paper", {})
    
    if (mode_override or "paper") == "live":
        # Provide real api keys if live, handled in executor
        backend_executor = LiveBackend(api_key=account_config.get("apiKey", ""), api_secret=account_config.get("apiSecret", ""))
    else:
        backend_executor = PaperBackend()
        
    # Route execution based on tool calls
    for tc in tool_calls:
        if tc["name"] == "place_order":
            args = tc.get("arguments", {})
            symbol = args.get("symbol", "UNKNOWN")
            side = args.get("side", "BUY")
            qty = float(args.get("qty", 0.0))
            
            # Execute through the robust backend which handles risk checks
            try:
                exec_result = backend_executor.execute_decision(symbol, side, qty)
                # The executor handles its own state updates (like updating positions in memory/json). 
                # For our new SQLite architecture, we log the trade if successful.
                if exec_result and exec_result.get("status") == "success":
                    trade = Trade(
                        timestamp=int(time.time()),
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        price=exec_result.get("price", 0.0)
                    )
                    session.add(trade)
                    decision.action = f"ORDER_{side}_{symbol}_SUCCESS"
                else:
                    decision.action = f"ORDER_{side}_{symbol}_FAILED"
            except Exception as e:
                decision.action = f"ORDER_{side}_{symbol}_ERROR_{str(e)}"
                
        session.commit()
```

- [x] **Step 3: Commit**
```bash
git add backend/engine_core.py
git commit -m "feat: route agent tool calls through robust ExecutionBackend"
```

### Task 2: Enhance System Prompt for Tool Usage

**Files:**
- Modify: `backend/engine_core.py`

- [x] **Step 1: Simplify `build_prompt`**
In `backend/engine_core.py`, locate the `build_prompt` function. Currently, it injects massive blocks of `market_context_str`. We need to strip this out and replace it with instructions to use tools.

```python
# In backend/engine_core.py, replace build_prompt logic:
def build_prompt(mode, account_state, market_data, custom_prompt, candidate_pool):
    # We ignore the massive market_data dump now.
    
    # Create a lean snapshot
    snapshot = f"Mode: {mode}\n"
    snapshot += f"Total Equity: {account_state.get('total_equity', 0)}\n"
    snapshot += f"Available Margin: {account_state.get('available_margin', 0)}\n"
    
    positions = account_state.get("positions", {})
    if positions:
        snapshot += "Open Positions:\n"
        for sym, pos in positions.items():
            snapshot += f"  - {sym}: {pos.get('side')} {pos.get('quantity')} @ {pos.get('entry_price')}\n"
    else:
        snapshot += "Open Positions: None\n"
        
    snapshot += "\nCandidate Universe:\n"
    for sym in candidate_pool:
        # Just give the symbol, the agent must use get_klines to get price data
        snapshot += f"  - {sym}\n"
        
    system_instruction = f"""You are an autonomous quantitative trading AI Agent.
Your goal is to maximize PnL while strictly managing risk.
{custom_prompt}

CURRENT ACCOUNT SNAPSHOT:
{snapshot}

INSTRUCTIONS:
1. You have a set of tools available. You MUST use them to gather information.
2. If you want to analyze a symbol, use the `get_klines` tool to fetch its historical data.
3. If you want to review your past mistakes or successes, use `get_recent_decisions`.
4. When you are ready to act, use `place_order` to execute a trade, or `pass_turn` if no action is needed.
5. Think step-by-step before calling a tool.
"""
    return system_instruction
```

- [x] **Step 2: Commit**
```bash
git add backend/engine_core.py
git commit -m "feat: refine system prompt for lean context and strict tool usage"
```