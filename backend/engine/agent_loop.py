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
            "update_position_risk": __import__('backend.engine.agent_tools', fromlist=['update_position_risk']).update_position_risk,
            "close_position": close_position,
            "pass_turn": pass_turn,
            "calculate_position_size": calculate_position_size,
            "calculate_kelly_position_size": calculate_kelly_position_size,
            "get_agent_performance_metrics": lambda: __import__('backend.engine.agent_tools', fromlist=['get_agent_performance_metrics']).get_agent_performance_metrics(self.Session),
            "scan_market_opportunities": lambda: __import__('backend.engine.agent_tools', fromlist=['scan_market_opportunities']).scan_market_opportunities(self.Session)
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
                terminal_action_taken = False
                for tool in response["tool_calls"]:
                    func = self.tools.get(tool["name"])
                    if func:
                        try:
                            result = func(**tool.get("arguments", {}))
                        except Exception as e:
                            result = {"error": str(e)}
                        self.history.append({
                            "role": "tool", 
                            "tool_call_id": tool.get("id", "call_123"),
                            "name": tool["name"], 
                            "content": json.dumps(result)
                        })
                        
                        if tool["name"] in ["place_order", "close_position", "update_position_risk", "pass_turn"]:
                            terminal_action_taken = True
                
                # If a terminal action was taken, end the reasoning loop early
                if terminal_action_taken:
                    return self.history
            else:
                return self.history
                
        # If loop exhausts without terminal action, force pass
        self.history.append({"role": "assistant", "tool_calls": [{"name": "pass_turn", "arguments": {}}]})
        return self.history
