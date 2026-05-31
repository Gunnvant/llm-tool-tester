"""Example tool definitions and test cases.

To add these to dataset.json, run:
    python add_test_case.py example_tools.py

This module demonstrates both the traditional TestCase construction
and the new TestCaseBuilder approach.
"""

from schema_gen import TestCaseBuilder, tool


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
# Test cases using TestCaseBuilder (recommended approach)
# ---------------------------------------------------------------------------

simple_weather = (
    TestCaseBuilder()
    .id("simple_weather_01")
    .category("simple")
    .description("Basic single tool call with required + optional arg")
    .system_message(DEFAULT_SYSTEM)
    .user_message("What is the weather like in Tokyo in celsius?")
    .add_tool(get_weather)
    .expect_tool_call(get_weather, city="Tokyo", unit="celsius")
    .evaluation_notes("Model must call get_weather. The user explicitly asks for celsius, so unit must be present.")
    .build()
)

parallel_search = (
    TestCaseBuilder()
    .id("parallel_search_01")
    .category("parallel")
    .description("Two independent tool calls in one turn")
    .system_message(DEFAULT_SYSTEM)
    .user_message("Calculate 2+2 and also get the weather in Paris.")
    .add_tool(calculator)
    .add_tool(get_weather)
    .expect_tool_call(calculator, expression="2+2")
    .expect_tool_call(get_weather, city="Paris")
    .evaluation_notes(
        "Order of tool_calls does not matter. Both must be present. "
        "The user did not specify a temperature unit, so unit is optional."
    )
    .build()
)

multiple_dependent = (
    TestCaseBuilder()
    .id("multiple_dependent_01")
    .category("multiple")
    .description("Sequential dependent calls (A then B, simulated in one turn)")
    .system_message(DEFAULT_SYSTEM)
    .user_message("Search the web for 'best Python IDE' and then calculate 10*5.")
    .add_tool(search_web)
    .add_tool(calculator)
    .expect_tool_call(search_web, query="best Python IDE")
    .expect_tool_call(calculator, expression="10*5")
    .evaluation_notes("Both calls must be present. The user did not specify num_results, so it is optional.")
    .build()
)

refusal_greeting = (
    TestCaseBuilder()
    .id("refusal_greeting_01")
    .category("refusal")
    .description("No tool needed; model should answer directly")
    .system_message(DEFAULT_SYSTEM)
    .user_message("Hello! How are you doing today?")
    .add_tool(get_weather)
    .expect_refusal("hello", "hi", "how are you")
    .evaluation_notes("Model must refuse to call tools and respond conversationally.")
    .build()
)
