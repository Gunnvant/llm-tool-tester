import requests

DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant with access to tools. "
    "When a user asks something that requires a tool, "
    "you MUST call the appropriate tool using the provided function format."
)


class LlamaClient:
    """Thin HTTP wrapper for llama-server's OpenAI-compatible endpoint.

    No abstractions: plain requests.post + JSON in/out.
    Auto-injects a system message when tools are present but no system
    message exists in the conversation.
    """

    def __init__(self, base_url: str, model_name: str = "local-model"):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.last_payload = None

    def chat_completion(
        self,
        messages: list,
        tools: list,
        temperature: float = 0.0,
        timeout: int = 120,
    ) -> dict:
        # Auto-inject system message if tools are present and no system msg exists
        has_system = any(m.get("role") == "system" for m in messages)
        if tools and not has_system:
            messages = [{"role": "system", "content": DEFAULT_SYSTEM_MESSAGE}] + list(messages)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        }
        self.last_payload = payload

        url = f"{self.base_url}/v1/chat/completions"
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
