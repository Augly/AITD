from backend.engine.agent_loop import ReActAgent

def mock_llm_call(prompt, tools):
    # Simulate LLM choosing a tool and then stopping
    if len(prompt) > 1 and prompt[-1]["role"] == "tool":
        return {"text": "Your balance is 10000 USDT"}
    return {"tool_calls": [{"name": "get_account_balance", "arguments": {}}]}

def test_agent_tool_calling_loop():
    agent = ReActAgent(llm_caller=mock_llm_call)
    response = agent.run("Check my balance")
    assert "USDT" in str(response)
