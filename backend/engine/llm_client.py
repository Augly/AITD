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
        
        # Convert our generic history to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "user":
                anthropic_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        content.append({
                            "type": "tool_use",
                            "id": tc.get("id", "call_123"),
                            "name": tc["name"],
                            "input": tc.get("arguments", {})
                        })
                anthropic_messages.append({"role": "assistant", "content": content})
            elif msg["role"] == "tool":
                # Anthropic expects tool results to be from the "user" role
                # But since we might have consecutive tool results, we should append them to a single user message if the last was also a user message with tool results,
                # but for simplicity, we just add a user message.
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", "call_123"),
                        "content": msg.get("content", "")
                    }]
                })
                
        # Merge consecutive user messages (Anthropic doesn't allow consecutive user messages without assistant in between, but tool_result is user role)
        merged_messages = []
        for am in anthropic_messages:
            if merged_messages and merged_messages[-1]["role"] == am["role"]:
                if isinstance(merged_messages[-1]["content"], list) and isinstance(am["content"], list):
                    merged_messages[-1]["content"].extend(am["content"])
                elif isinstance(merged_messages[-1]["content"], str) and isinstance(am["content"], list):
                    merged_messages[-1]["content"] = [{"type": "text", "text": merged_messages[-1]["content"]}] + am["content"]
                elif isinstance(merged_messages[-1]["content"], list) and isinstance(am["content"], str):
                    merged_messages[-1]["content"].append({"type": "text", "text": am["content"]})
                else:
                    merged_messages[-1]["content"] += "\n" + am["content"]
            else:
                merged_messages.append(am)
        
        data = {
            "model": "claude-3-5-sonnet-20240620",
            "max_tokens": 1024,
            "messages": merged_messages,
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
                            "id": block.get("id", "call_123"),
                            "name": block["name"],
                            "arguments": block.get("input", {})
                        })
                return result
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2 ** attempt)

class OpenAIClient:
    def __init__(self, api_key, base_url="https://api.openai.com/v1/chat/completions", model="gpt-4o"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
    def call(self, messages, tools, retries=3):
        import time
        req = urllib.request.Request(self.base_url, method="POST")
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
            
        # Convert our generic history to OpenAI format
        openai_messages = []
        for msg in messages:
            if msg["role"] == "user":
                openai_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                ast_msg = {"role": "assistant", "content": msg.get("content", "")}
                if msg.get("tool_calls"):
                    ast_msg["tool_calls"] = []
                    for tc in msg["tool_calls"]:
                        ast_msg["tool_calls"].append({
                            "id": tc.get("id", "call_123"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("arguments", {}))
                            }
                        })
                openai_messages.append(ast_msg)
            elif msg["role"] == "tool":
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", "call_123"),
                    "name": msg.get("name", "unknown"),
                    "content": msg.get("content", "")
                })

        data = {
            "model": self.model,
            "messages": openai_messages,
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
                    "id": tc.get("id", "call_123"),
                    "name": tc["function"]["name"],
                    "arguments": args
                })
        return result

class LLMClientFactory:
    @staticmethod
    def create(provider: str, api_key: str):
        if provider.lower() == "anthropic":
            return AnthropicClient(api_key)
        elif provider.lower() == "openai":
            return OpenAIClient(api_key)
        elif provider.lower() == "deepseek":
            return OpenAIClient(api_key, base_url="https://api.deepseek.com/chat/completions", model="deepseek-chat")
        raise ValueError(f"Unknown provider: {provider}")
