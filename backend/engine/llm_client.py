import json
import urllib.request

class AnthropicClient:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def call(self, messages, tools, retries=3):
        import time
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="POST")
        req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("content-type", "application/json")
        
        data = {
            "model": "claude-3-5-sonnet-20240620",
            "max_tokens": 1024,
            "messages": messages,
            "tools": tools
        }
        
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'), timeout=30) as response:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    
                result = {"text": "", "tool_calls": []}
                for block in resp_data.get("content", []):
                    if block["type"] == "text":
                        result["text"] += block["text"]
                    elif block["type"] == "tool_use":
                        result["tool_calls"].append({
                            "name": block["name"],
                            "arguments": block["input"]
                        })
                return result
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2 ** attempt)

class OpenAIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def call(self, messages, tools, retries=3):
        import time
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        
        # Convert Anthropic tool schema to OpenAI function calling schema
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}})
                }
            })
            
        data = {
            "model": "gpt-4o",
            "messages": messages,
            "tools": openai_tools if openai_tools else None
        }
        if not data["tools"]:
            del data["tools"]
            
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'), timeout=30) as response:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    return self._standardize_response(resp_data)
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2 ** attempt)
        
    def _standardize_response(self, response_dict):
        message = response_dict["choices"][0]["message"]
        result = {"text": message.get("content", "") or "", "tool_calls": []}
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                result["tool_calls"].append({
                    "name": tc["function"]["name"],
                    "arguments": args
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
