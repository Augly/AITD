# Phase 2: Agent Tool-Use Loop & LLM Client Abstraction

## 1. Overview
The goal of Phase 2 is to transform the LLM interaction from a single monolithic prompt (which included all historical data) into a lean, dynamic tool-use loop. The agent will receive only a small context snapshot (~2-3k tokens) and will autonomously call tools to fetch detailed K-lines, past decisions, or execute trades. We will implement a custom `LLMClient` factory to standardize tool-calling across Anthropic, OpenAI, and DeepSeek.

## 2. Database Additions (SQLAlchemy)
We will expand on the Phase 1 database setup.
- **New Tables**:
  - `Decision`: Tracks every decision made by the agent (id, timestamp, symbol, action, reasoning).
  - `Trade`: Tracks executed trades and their PnL.
- **Sync Worker Updates**:
  - Ensure the `sync_worker.py` runs an incremental K-line fetch every 5 minutes for the candidate universe.

## 3. Agent Context Shrinking
The monolithic prompt will be stripped down. The system message and initial user message will ONLY contain:
1. **Account/Position Snapshot**: Available margin, open positions, current PnL (~500 tokens).
2. **Candidate Universe**: A list of active symbols and their latest prices (~1k tokens).
3. **Recent Memory**: The last 5 decision summaries from the agent (~1k tokens).

## 4. Tool Registry (The Agent's Arsenal)
We will expose 8 specific tools to the LLM:
1. `list_universe()`: Returns the list of available symbols to trade.
2. `get_klines(symbol, interval, limit)`: Fetches historical K-lines from the local SQLite cache.
3. `get_account()`: Fetches real-time account balances and equity.
4. `get_position(symbol)`: Returns detailed position data (entry price, leverage, PnL) for a specific asset.
5. `get_recent_decisions(limit)`: Fetches the last N decisions from the agent memory table.
6. `place_order(symbol, side, qty)`: Executes a trade (Paper/Live).
7. `close_position(symbol)`: Closes an existing position.
8. `pass()`: Indicates the agent has finished thinking and has decided to take no action this cycle.

## 5. LLM Client Abstraction Layer
A custom `LLMClient` factory to handle multiple providers gracefully without bloated dependencies.
- **AnthropicClient**: Native support for the Anthropic Tool-Use API schema.
- **OpenAIClient / DeepSeekClient**: Wraps the OpenAI Function Calling API. The wrapper will parse the OpenAI response and translate the `function_call` objects into the same standardized dictionary format outputted by the Anthropic client.
- **Standardized Output**: Both clients will return a unified response object to the ReAct loop: `{"text": "...", "tool_calls": [{"name": "...", "arguments": {...}}]}`.

## 6. End-to-End Paper Mode
- The system will be wired up to run fully end-to-end in "Paper" mode.
- The 5-minute sync worker will populate the database.
- The 15-minute agent loop will wake up, evaluate the lean context, call tools (e.g., `get_klines` for a symbol it finds interesting), and execute `place_order` or `pass()`.
- Trades will be simulated locally and recorded in the SQLite database.
