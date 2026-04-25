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
