# Phase 6: Final Execution Engine Integration

## 1. Overview
The goal of Phase 6 is to complete the transition from a monolithic script to a fully autonomous, production-ready AI Agent trading platform. We will replace all remaining tool stubs with real API/DB calls and connect the ReAct agent's `tool_calls` directly to the `executor.py` backend. This ensures all safety mechanisms (margin caps, circuit breakers) are enforced before a trade is executed. Additionally, we will drastically reduce the LLM system prompt size to force the Agent to rely on tool calls for detailed market data.

## 2. Real Account Tools Implementation
The `agent_tools.py` file currently contains stubs for account and position queries. We will replace these:
- **`list_universe()`**: Read the dynamic candidate universe from `backend/config.py` (`read_fixed_universe()`).
- **`get_account_balance()`**: Depending on the trading mode (Paper/Live), this will fetch the simulated balance from SQLite or the real balance from `BinanceGateway.fetch_account_snapshot()`.
- **`get_position(symbol)`**: Query the SQLite database (or live exchange) for open positions and their unrealized PnL.

## 3. Execution Engine Integration
The ReAct Agent outputs a final `place_order(symbol, side, qty)` tool call. Currently, this just writes a dummy row to the `Trade` table.
We will refactor `engine_core.py`:
- **Instantiate Execution Backend**: Based on the mode (`live` or `paper`), instantiate `LiveBackend` or `PaperBackend` from `backend/engine/executor.py`.
- **Route Tool Calls**: When the Agent outputs a `place_order` tool call, translate it into an `execute_decision()` call on the instantiated backend. The backend will handle:
  - Validating margin and drawdown limits.
  - Calling the actual Binance API (if live) or updating the local paper state (if paper).
  - Logging the trade to the `Trade` SQLite table automatically.

## 4. Prompt Context Shrinking
The old system prompt injected hundreds of lines of historical K-lines for every symbol in the universe. This is no longer necessary and breaks the ReAct pattern.
We will update `build_prompt` in `engine_core.py`:
- **Remove**: Historical K-line dump.
- **Include**: 
  - A brief snapshot of the account equity.
  - A list of available symbols in the universe and their latest ticker prices.
  - The last 5 reasoning summaries from the Agent (fetched via `get_recent_decisions()`).
- **Instructions**: Explicitly instruct the LLM: "You have tools available. If you need historical K-lines for a symbol, use `get_klines`. Do not guess."

## 5. End-to-End Validation
Once integrated, the system will run a full paper trading cycle:
1. `SyncWorker` fetches K-lines.
2. `ReActAgent` wakes up, reads the lean prompt, and calls `get_klines` for an interesting symbol.
3. `ReActAgent` decides to buy, outputting a `place_order` tool call.
4. `engine_core.py` routes the call to `PaperBackend`.
5. `PaperBackend` checks margin, executes the trade, and updates the SQLite database.
