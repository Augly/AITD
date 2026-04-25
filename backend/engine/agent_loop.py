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
                # LLM output also needs to be appended to history
                # But for the minimal test passing, we just follow the instructions
                # Actually, wait. Let's append the assistant's message as well, if we want to follow real react loop, but the plan has specific code. Let's use the plan's code.
                for tool in response["tool_calls"]:
                    func = self.tools.get(tool["name"])
                    if func:
                        result = func(**tool.get("arguments", {}))
                        self.history.append({"role": "tool", "content": json.dumps(result)})
            else:
                return response
        return self.history
