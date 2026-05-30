"""Example tool definitions and test cases.

To add these to dataset.json, run:
    python add_test_case.py example_tools.py
"""

from schema_gen import TestCase, tool


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get the current weather for a given location."""
    pass


@tool
def calculator(expression: str) -> float:
    """Evaluate a mathematical expression."""
    pass


@tool
def search_web(query: str, num_results: int = 5) -> list:
    """Search the web for a query."""
    pass


DEFAULT_SYSTEM = (
    "You are a helpful assistant with access to tools. "
    "When a user asks something that requires a tool, "
    "you MUST call the appropriate tool using the provided function format."
)


# ---------------------------------------------------------------------------
# Test cases that will be discovered by add_test_case.py
# ---------------------------------------------------------------------------

simple_weather = TestCase(
    id="simple_weather_01",
    category="simple",
    description="Basic single tool call",
    system_message=DEFAULT_SYSTEM,
    messages=[{"role": "user", "content": "What is the weather like in Tokyo in celsius?"}],
    tools=[get_weather],
    expected={
        "should_call_tools": True,
        "tool_calls": [{"name": "get_weather", "arguments": {"city": "Tokyo", "unit": "celsius"}}],
    },
    evaluation_notes="Model must call get_weather with city and unit.",
)

parallel_search = TestCase(
    id="parallel_search_01",
    category="parallel",
    description="Two independent tool calls in one turn",
    system_message=DEFAULT_SYSTEM,
    messages=[{"role": "user", "content": "Calculate 2+2 and also get the weather in Paris."}],
    tools=[calculator, get_weather],
    expected={
        "should_call_tools": True,
        "tool_calls": [
            {"name": "calculator", "arguments": {"expression": "2+2"}},
            {"name": "get_weather", "arguments": {"city": "Paris"}},
        ],
    },
    evaluation_notes="Order does not matter. Both calls must be present.",
)

multiple_dependent = TestCase(
    id="multiple_dependent_01",
    category="multiple",
    description="Sequential dependent calls in one turn",
    system_message=DEFAULT_SYSTEM,
    messages=[{"role": "user", "content": "Search the web for 'best Python IDE' and then calculate 10*5."}],
    tools=[search_web, calculator],
    expected={
        "should_call_tools": True,
        "tool_calls": [
            {"name": "search_web", "arguments": {"query": "best Python IDE"}},
            {"name": "calculator", "arguments": {"expression": "10*5"}},
        ],
    },
    evaluation_notes="Both calls must be present.",
)

refusal_greeting = TestCase(
    id="refusal_greeting_01",
    category="refusal",
    description="Model should not call tools",
    system_message=DEFAULT_SYSTEM,
    messages=[{"role": "user", "content": "Hello! How are you doing today?"}],
    tools=[get_weather],
    expected={
        "should_call_tools": False,
        "tool_calls": [],
        "content_must_contain": ["hello", "hi", "how are you"],
    },
    evaluation_notes="Model must respond conversationally without calling tools.",
)
