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


class TestCaseBuilder:
    """Fluent builder for TestCase objects."""

    def __init__(self):
        self._id = None
        self._category = None
        self._description = ""
        self._messages = []
        self._tools = []
        self._expected_tool_calls = []
        self._should_call_tools = None
        self._content_must_contain = None
        self._evaluation_notes = ""
        self._system_message = ""

    def id(self, id_str: str):
        self._id = id_str
        return self

    def category(self, cat: str):
        self._category = cat
        return self

    def description(self, desc: str):
        self._description = desc
        return self

    def system_message(self, msg: str):
        self._system_message = msg
        return self

    def user_message(self, content: str):
        self._messages.append({"role": "user", "content": content})
        return self

    def assistant_message(self, content: str):
        self._messages.append({"role": "assistant", "content": content})
        return self

    def add_tool(self, tool_callable: Callable):
        self._tools.append(tool_callable)
        return self

    def expect_tool_call(self, tool_callable: Callable, **kwargs):
        """Add expected tool call. Infers name from callable, uses kwargs as arguments."""
        self._expected_tool_calls.append({"name": tool_callable.__name__, "arguments": kwargs})
        self._should_call_tools = True
        return self

    def expect_refusal(self, *content_phrases):
        """Set expectation to refuse tool calls, with phrases to check in response."""
        self._should_call_tools = False
        self._content_must_contain = list(content_phrases)
        return self

    def evaluation_notes(self, notes: str):
        self._evaluation_notes = notes
        return self

    def build(self) -> TestCase:
        """Validate and build the TestCase object."""
        if not self._id:
            raise ValueError("id is required")
        if not self._category:
            raise ValueError("category is required")
        if not self._messages:
            raise ValueError("at least one message is required")
        if self._should_call_tools is None:
            raise ValueError("must call expect_tool_call() or expect_refusal()")
        if self._should_call_tools and not self._tools:
            raise ValueError("tools are required when expecting tool calls")

        expected = {"should_call_tools": self._should_call_tools}
        if self._should_call_tools:
            expected["tool_calls"] = self._expected_tool_calls
        else:
            expected["tool_calls"] = []
            if self._content_must_contain:
                expected["content_must_contain"] = self._content_must_contain

        return TestCase(
            id=self._id,
            category=self._category,
            description=self._description,
            messages=self._messages,
            tools=self._tools,
            expected=expected,
            evaluation_notes=self._evaluation_notes,
            system_message=self._system_message,
        )


def simple_test_case(id: str, category: str, question: str, tool_callable: Callable, expected_args: dict, **kwargs):
    """Create a single-tool-call test case."""
    builder = TestCaseBuilder()
    builder.id(id).category(category).user_message(question).add_tool(tool_callable)
    builder.expect_tool_call(tool_callable, **expected_args)
    for key, value in kwargs.items():
        if hasattr(builder, key):
            getattr(builder, key)(value)
        else:
            raise AttributeError(f"TestCaseBuilder has no attribute {key}")
    return builder.build()


def refusal_test_case(id: str, category: str, question: str, tools: list, content_phrases: list, **kwargs):
    """Create a refusal test case (no tool calls expected)."""
    builder = TestCaseBuilder()
    builder.id(id).category(category).user_message(question)
    for tool in tools:
        builder.add_tool(tool)
    builder.expect_refusal(*content_phrases)
    for key, value in kwargs.items():
        if hasattr(builder, key):
            getattr(builder, key)(value)
        else:
            raise AttributeError(f"TestCaseBuilder has no attribute {key}")
    return builder.build()


def parallel_test_case(id: str, category: str, question: str, tool_call_pairs: list, **kwargs):
    """Create a multi-tool-call test case. tool_call_pairs: list of (tool_callable, args_dict)"""
    builder = TestCaseBuilder()
    builder.id(id).category(category).user_message(question)
    for tool_callable, args in tool_call_pairs:
        builder.add_tool(tool_callable)
        builder.expect_tool_call(tool_callable, **args)
    for key, value in kwargs.items():
        if hasattr(builder, key):
            getattr(builder, key)(value)
        else:
            raise AttributeError(f"TestCaseBuilder has no attribute {key}")
    return builder.build()
