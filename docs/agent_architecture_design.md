# AITD Agent Architecture Design Spec

## 1. Overview
The goal is to transform the current AITD system from a template-based single-call script into a true **LLM-driven Autonomous Trading AI Agent**. 
The new system will feature a custom ReAct (Reasoning + Acting) loop, a persistent SQLite database replacing JSON files, a decoupled background data synchronization worker, and an expanded toolset for multi-step reasoning, memory retrieval, and self-reflection.

## 2. Architecture & Components

### 2.1 Database Layer (SQLite + SQLAlchemy)
Replaces the fragile `trading_agent_state.json`.
- **Tables**:
  - `KLineCache`: Stores historical and real-time K-line data synchronized by the background worker.
  - `AgentMemory`: Stores past agent reasoning logs, trade outcomes, and reflections.
  - `TradeHistory`: Records all executed trades (paper and live).
  - `Positions`: Current open positions.

### 2.2 Data Synchronization Worker (Background)
A decoupled, asynchronous background process that:
- Periodically polls the exchange for K-line data, order book depth, and tickers (e.g., every 1 minute).
- Persists this data into the `KLineCache` database table.
- Monitors price action for anomalies (e.g., >3% move within 5 minutes) and fires an **Anomaly Trigger** event to wake up the Agent.

### 2.3 Autonomous Agent Core (Custom ReAct Loop)
Replaces the monolithic `engine.py`. Implements a lightweight, custom tool-calling loop:
1. **Trigger**: Time-based (e.g., 15 mins) or Event-based (price anomaly).
2. **Context Assembly**: Load system prompt, current account balance, and open positions.
3. **Loop**:
   - **Think**: LLM analyzes the situation and decides which tool to call.
   - **Action**: LLM outputs a tool call (JSON).
   - **Observation**: System executes the tool and appends the result to the conversation history.
4. **Final Decision**: The LLM outputs a final trading action (Open, Close, Reduce, Hold) along with its reasoning.

### 2.4 Toolset Expansion
The Agent will have access to the following tools:
- **Market & Indicators**: `get_kline_data(symbol, interval, limit)`, `get_orderbook(symbol)`, `calculate_indicator(data, type)`.
- **Account & Position**: `get_account_balance()`, `get_open_positions()`.
- **Memory & Reflection**: `query_past_decisions(symbol)`, `log_reflection(text)`.
- **News & Sentiment**: `search_news(symbol)` (Mock or real API).
- **Execution**: `execute_trade(symbol, side, quantity, type)`.

## 3. Data Flow
1. **Sync Phase**: Background worker fetches market data -> Saves to SQLite.
2. **Trigger Phase**: 15-min timer OR price anomaly event -> Wakes up Agent.
3. **Reasoning Phase**: Agent requests K-lines via `get_kline_data` tool -> Reads from SQLite -> Calculates indicators -> Queries memory -> Formulates plan.
4. **Execution Phase**: Agent outputs `execute_trade` -> System validates risk -> Sends API request to Exchange -> Saves result to `TradeHistory` and `Positions`.

## 4. Error Handling & Risk Management
- **Connection Pooling & Retries**: All HTTP requests to exchanges will use connection pooling (`httpx` or `requests.Session`) with exponential backoff.
- **Database Locks**: SQLAlchemy will handle concurrent reads/writes safely, eliminating JSON TOCTOU (Time-of-Check to Time-of-Use) bugs.
- **Circuit Breaker**: A strict, independent risk management layer that intercepts any `execute_trade` tool call from the LLM. If maximum drawdown is breached, the trade is rejected.
- **Fallback**: If the LLM enters an infinite tool-calling loop, it will be forcefully terminated after a maximum number of iterations (e.g., 10) and default to "Hold".

## 5. Testing Strategy
- **Unit Tests**: Mock the LLM responses to test the custom ReAct loop's ability to parse tool calls and handle tool errors.
- **Database Tests**: Verify SQLAlchemy schema migrations and concurrent read/write safety between the Sync Worker and the Agent.
- **Integration Tests**: End-to-end paper trading tests using historical K-line data seeded into the SQLite database.

## 6. Phasing
1. **Phase 1**: Database Setup (SQLAlchemy) & Migration from JSON.
2. **Phase 2**: Background Sync Worker & Event Trigger System.
3. **Phase 3**: Agent Core (ReAct loop) & Tool Implementation.
4. **Phase 4**: Refactor API Server to support the new Agent state and logging.