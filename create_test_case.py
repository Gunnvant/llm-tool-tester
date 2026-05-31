"""Interactive CLI wizard for creating test cases.

Guides the user through creating a TestCase and saves it directly
to dataset.json using the Dataset class.
"""

import inspect
import json
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset import Dataset  # noqa: E402
from schema_gen import TestCaseBuilder  # noqa: E402


def load_module(module_path: str):
    """Load a Python module from file path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("tool_module", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tool_module"] = mod
    spec.loader.exec_module(mod)
    return mod


def get_tool_functions(module):
    """Get all tool functions from a module."""
    tools = []
    for name in dir(module):
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, "__name__"):
            tools.append(obj)
    return tools


def load_dataset(dataset_path: str = "dataset.json"):
    """Load existing dataset and return test IDs and categories."""
    if os.path.exists(dataset_path):
        with open(dataset_path) as f:
            data = json.load(f)
        ids = {tc["id"] for tc in data["test_cases"]}
        categories = {tc["category"] for tc in data["test_cases"]}
        return ids, categories
    return set(), set()


def prompt(question: str, default: str = "", required: bool = True) -> str:
    """Prompt user for input."""
    question = f"{question} [{default}]: " if default else f"{question}: "
    while True:
        value = input(question).strip()
        if not value:
            value = default
        if required and not value:
            print("This field is required.")
            continue
        return value


def prompt_bool(question: str, default: bool = False) -> bool:
    """Prompt user for yes/no."""
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{question} [{default_str}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")


def select_tool(tools):
    """Let user select a tool from available tools."""
    print("\nAvailable tools:")
    for i, tool in enumerate(tools, 1):
        sig = inspect.signature(tool)
        params = list(sig.parameters.keys())
        print(f"  {i}. {tool.__name__}({', '.join(params)}) - {tool.__doc__ or ''}")

    while True:
        try:
            choice = int(input(f"\nSelect tool (1-{len(tools)}): ").strip())
            if 1 <= choice <= len(tools):
                return tools[choice - 1]
            print(f"Please enter a number between 1 and {len(tools)}.")
        except ValueError:
            print("Please enter a valid number.")


def get_tool_args(tool_func, action: str = "call"):
    """Interactively prompt for tool arguments."""
    sig = inspect.signature(tool_func)
    args = {}
    print(f"\nEnter arguments for {tool_func.__name__} (press Enter to skip optional args):")
    for name, param in sig.parameters.items():
        has_default = param.default != inspect.Parameter.empty
        prompt_text = f"  {name} (optional, default={param.default})" if has_default else f"  {name} (required)"
        value = input(f"{prompt_text}: ").strip()
        if value:
            args[name] = value
        elif has_default:
            args[name] = param.default
    return args


def main():
    print("=" * 60)
    print("  Test Case Creator - Interactive Wizard")
    print("=" * 60)

    # Load existing dataset
    dataset = Dataset()
    if os.path.exists("dataset.json"):
        dataset.load()

    existing_ids = {tc.id for tc in dataset.test_cases}
    existing_categories = {tc.category for tc in dataset.test_cases}

    # Get test ID
    while True:
        test_id = prompt("Test ID (e.g., my_test_01)")
        if test_id in existing_ids:
            print(f"Warning: '{test_id}' already exists in dataset.json.")
            if not prompt_bool("Overwrite existing test?", False):
                continue
        break

    # Get category
    if existing_categories:
        print(f"\nExisting categories: {', '.join(sorted(existing_categories))}")
    category = prompt("Category")

    # Description
    description = prompt("Description (optional)", required=False)

    # System message
    default_system = (
        "You are a helpful assistant with access to tools. "
        "When a user asks something that requires a tool, "
        "you MUST call the appropriate tool using the provided function format."
    )
    print(f"\nDefault system message:\n  {default_system}")
    if prompt_bool("Use default system message?", True):
        system_message = default_system
    else:
        system_message = prompt("Enter system message", required=False)

    # User message
    user_message = prompt("User message (the test prompt)")

    # Load tools module
    tools_module_path = prompt("Tools module path", default="test_cases.py", required=False)
    if tools_module_path and os.path.exists(tools_module_path):
        tools_module = load_module(tools_module_path)
        tools = get_tool_functions(tools_module)
        if not tools:
            print("No tool functions found in module.")
            tools = []
    else:
        print("Tools module not found. Proceeding without tools.")
        tools = []

    # Select tools
    selected_tools = []
    if tools:
        print("\nSelect tools for this test case:")
        while True:
            tool = select_tool(tools)
            selected_tools.append(tool)
            if not prompt_bool("Add another tool?", False):
                break

    # Expected behavior
    print("\nExpected behavior:")
    print("  1. Model should call tools")
    print("  2. Model should refuse (no tool calls)")
    while True:
        choice = input("Select (1-2): ").strip()
        if choice == "1":
            expected_behavior = "tool_calls"
            break
        elif choice == "2":
            expected_behavior = "refusal"
            break
        print("Please enter 1 or 2.")

    # Build expected tool calls
    expected_tool_calls = []
    if expected_behavior == "tool_calls":
        print("\nBuild expected tool calls:")
        for tool in selected_tools:
            if prompt_bool(f"Expect call to {tool.__name__}?", True):
                args = get_tool_args(tool)
                expected_tool_calls.append((tool, args))
    else:
        # Refusal - get content phrases
        content_phrases_str = prompt("Content phrases to check (comma-separated)", required=False)
        content_phrases = [p.strip() for p in content_phrases_str.split(",") if p.strip()]

    # Evaluation notes
    evaluation_notes = prompt("Evaluation notes (optional)", required=False)

    # Build the test case
    print("\n" + "=" * 60)
    print("Building test case...")
    print("=" * 60)

    builder = TestCaseBuilder()
    builder.id(test_id).category(category)
    if description:
        builder.description(description)
    if system_message:
        builder.system_message(system_message)
    builder.user_message(user_message)

    for tool in selected_tools:
        builder.add_tool(tool)

    if expected_behavior == "tool_calls":
        for tool, args in expected_tool_calls:
            builder.expect_tool_call(tool, **args)
    else:
        if content_phrases:
            builder.expect_refusal(*content_phrases)

    if evaluation_notes:
        builder.evaluation_notes(evaluation_notes)

    test_case = builder.build()

    # Add to dataset
    if test_id in existing_ids:
        dataset.update(test_id, test_case)
        print(f"Updated test case: {test_id}")
    else:
        dataset.add(test_case)
        print(f"Added test case: {test_id}")

    # Save to dataset.json
    dataset.save()
    print(f"\nSaved {len(dataset)} test cases to dataset.json")
    print("\nDone!")


if __name__ == "__main__":
    main()
