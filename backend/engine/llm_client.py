import json

class AnthropicClient:
    def __init__(self, api_key):
        self.api_key = api_key
    def call(self, messages, tools):
        pass # Stub for actual network call

class OpenAIClient:
    def __init__(self, api_key):
        self.api_key = api_key
    def call(self, messages, tools):
        pass # Stub for actual network call
        
    def _standardize_response(self, response_dict):
        message = response_dict["choices"][0]["message"]
        result = {"text": message.get("content", "") or "", "tool_calls": []}
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                result["tool_calls"].append({
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"])
                })
        return result

class LLMClientFactory:
    @staticmethod
    def create(provider: str, api_key: str):
        if provider.lower() == "anthropic":
            return AnthropicClient(api_key)
        elif provider.lower() in ["openai", "deepseek"]:
            return OpenAIClient(api_key)
        raise ValueError(f"Unknown provider: {provider}")
