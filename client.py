from openai import OpenAI

DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant with access to tools. "
    "When a user asks something that requires a tool, "
    "you MUST call the appropriate tool using the provided function format."
)


class LlamaClient:
    """Thin wrapper around the official OpenAI client for llama-server."""

    def __init__(self, base_url: str, model_name: str = "local-model"):
        self.client = OpenAI(
            base_url=base_url.rstrip("/") + "/v1",
            api_key="not-needed",
        )
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

        self.last_payload = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        }

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=tools or None,
            tool_choice="auto",
            temperature=temperature,
            timeout=timeout,
        )
        return response.model_dump()
