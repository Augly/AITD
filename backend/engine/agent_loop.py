import json
from backend.engine.agent_tools import (
    get_account_balance,
    get_position,
    get_recent_decisions,
    get_kline_data,
    analyze_market_technicals,
    list_universe,
    place_order,
    close_position,
    pass_turn,
    calculate_position_size,
    calculate_kelly_position_size,
    analyze_multi_timeframe
)
from backend.engine.db import init_db

class ReActAgent:
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
        self.Session = init_db()
        
        # We wrap tools that require session_factory
        self.tools = {
            "get_account_balance": get_account_balance,
            "get_position": get_position,
            "get_recent_decisions": lambda limit=5: get_recent_decisions(limit, self.Session),
            "get_kline_data": lambda symbol, interval="15m", limit=100: get_kline_data(symbol, interval, self.Session, limit),
            "analyze_market_technicals": lambda symbol, interval="15m": analyze_market_technicals(symbol, interval, self.Session),
            "analyze_multi_timeframe": lambda symbol: analyze_multi_timeframe(symbol, self.Session),
            "list_universe": list_universe,
            "place_order": place_order,
            "close_position": close_position,
            "pass_turn": pass_turn,
            "calculate_position_size": calculate_position_size,
            "calculate_kelly_position_size": calculate_kelly_position_size
        }
        self.history = []

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
