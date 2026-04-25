import pytest
from backend.engine.llm_client import LLMClientFactory, AnthropicClient, OpenAIClient

def test_factory_creates_correct_client():
    anthropic = LLMClientFactory.create("anthropic", "api_key")
    assert isinstance(anthropic, AnthropicClient)
    openai = LLMClientFactory.create("openai", "api_key")
    assert isinstance(openai, OpenAIClient)

def test_openai_format_translation():
    client = OpenAIClient("fake_key")
    # Simulate an OpenAI function call response
    mock_response = {
        "choices": [{
            "message": {
                "content": "Thinking...",
                "tool_calls": [{
                    "function": {"name": "get_klines", "arguments": "{\"symbol\":\"BTCUSDT\"}"}
                }]
            }
        }]
    }
    standardized = client._standardize_response(mock_response)
    assert standardized["text"] == "Thinking..."
    assert standardized["tool_calls"][0]["name"] == "get_klines"
    assert standardized["tool_calls"][0]["arguments"]["symbol"] == "BTCUSDT"
