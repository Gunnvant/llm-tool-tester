from collections.abc import Callable

from function_schema import get_function_schema


def get_tool_schema(func: Callable) -> dict:
    """Generate an OpenAI-compatible tool schema from a Python function.

    Uses function-schema to extract name, description, and parameters
    from type hints and docstrings.
    """
    schema = get_function_schema(func)
    return {"type": "function", "function": schema}


def tool(func: Callable) -> Callable:
    """No-op decorator to visually mark a function as a tool.

    This makes example_tools.py self-documenting.
    """
    return func


class TestCase:
    """Represents a single evaluation case.

    Tools are stored as live callables so that add_test_case.py can
    auto-generate their JSON schemas.  to_dict() produces the plain
    JSON representation that dataset.json expects.
    """

    def __init__(
        self,
        id: str,
        category: str,
        description: str,
        messages: list[dict],
        tools: list[Callable],
        expected: dict,
        evaluation_notes: str = "",
        system_message: str = "",
    ):
        self.id = id
        self.category = category
        self.description = description
        self.messages = messages
        self.tools = tools
        self.expected = expected
        self.evaluation_notes = evaluation_notes
        self.system_message = system_message

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "messages": self.messages,
            "tools": [get_tool_schema(t) for t in self.tools],
            "expected": self.expected,
            "evaluation_notes": self.evaluation_notes,
        }
        if self.system_message:
            result["system_message"] = self.system_message
        return result
