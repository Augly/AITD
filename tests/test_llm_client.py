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

from unittest.mock import patch
import json

@patch('urllib.request.urlopen')
def test_anthropic_real_call(mock_urlopen):
    from backend.engine.llm_client import AnthropicClient
    class MockResponse:
        def read(self):
            return json.dumps({
                "content": [{"type": "text", "text": "Thinking..."}, {"type": "tool_use", "name": "pass_turn", "input": {}}]
            }).encode('utf-8')
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_urlopen.return_value = MockResponse()
    
    client = AnthropicClient("fake_key")
    res = client.call([{"role": "user", "content": "test"}], [])
    assert res["text"] == "Thinking..."
    assert res["tool_calls"][0]["name"] == "pass_turn"

@patch('urllib.request.urlopen')
def test_openai_real_call(mock_urlopen):
    from backend.engine.llm_client import OpenAIClient
    class MockResponse:
        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {
                        "content": "Thinking...",
                        "tool_calls": [{
                            "function": {"name": "place_order", "arguments": "{\"symbol\":\"BTCUSDT\",\"side\":\"BUY\",\"qty\":1.0}"}
                        }]
                    }
                }]
            }).encode('utf-8')
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    mock_urlopen.return_value = MockResponse()
    
    client = OpenAIClient("fake_key")
    res = client.call([{"role": "user", "content": "test"}], [])
    assert res["text"] == "Thinking..."
    assert res["tool_calls"][0]["name"] == "place_order"
    assert res["tool_calls"][0]["arguments"]["side"] == "BUY"
