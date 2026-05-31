# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A pure-Python framework for testing tool-calling capabilities of local LLMs served by `llama.cpp` (`llama-server`). It sends test prompts via raw HTTP to the OpenAI-compatible `/v1/chat/completions` endpoint and scores responses against ground-truth expectations.

## Common Commands

### Run the full evaluation suite
```bash
python run_tests.py --config config.yaml --dataset dataset.json --output results.json
```

### Run for specific models only
```bash
python run_tests.py --config config.yaml --dataset dataset.json --models qwen2.5-3b-it
```

### Debug a single test case (requires an already-running server)
```bash
python debug_single.py --model <model_name> --test-id <test_id>
```

### Create test cases interactivly
```bash
python create_test_case.py
```

### Create test cases with TestCaseBuilder (Python/Jupyter)
```python
from schema_gen import TestCaseBuilder
test = (TestCaseBuilder()
    .id("my_test_01")
    .category("simple")
    .user_message("What is the weather in Tokyo?")
    .add_tool(get_weather)
    .expect_tool_call(get_weather, city="Tokyo")
    .build()
)
```

### Serialize test cases to dataset.json
```bash
python test_cases.py
```

### Create test cases interactively
```bash
python create_test_case.py
```

### Create test cases with TestCaseBuilder (Python/Jupyter)
```python
from schema_gen import TestCaseBuilder
test = (TestCaseBuilder()
    .id("my_test_01")
    .category("simple")
    .user_message("What is the weather in Tokyo?")
    .add_tool(get_weather)
    .expect_tool_call(get_weather, city="Tokyo")
    .build()
)
```

### Start llama-server manually for debugging
```bash
llama-server --jinja -m ./models/<model>.gguf --port 8080 -c 4096 --chat-template <template>
```

### Install dependencies
```bash
uv sync
source .venv/bin/activate
```

After activation, you can run `python` commands directly.

### JupyterLab notebooks
- `notebooks/tool_calling_debug.ipynb` — Debugging tool-calling request structures against `llama-server`.
- `notebooks/test_case_builder.ipynb` — Creating and previewing test cases with `TestCaseBuilder` and helpers.

**Register the kernel once:**
```bash
python -m ipykernel install --name llm-tool-tester --display-name "Python (llm-tool-tester)" --user
```

**Launch:**
```bash
jupyter lab notebooks/
```

### Run linters
```bash
# Check all code
python -m ruff check . && python -m flake8 --config .flake8 . && python -m isort --check-only --diff .

# Auto-fix issues
python -m ruff check . --fix
python -m isort .
python -m ruff format .
```

> **Pre-commit hook:** `.git/hooks/pre-commit` automatically runs `isort`, `ruff` (check + format check), and `flake8` on staged Python files via `uv run`. If any check fails, the commit is blocked.

## High-Level Architecture

The framework has four conceptual layers that are deliberately thin:

1. **Server Layer (`server_manager.py`)**
   - `LlamaServerManager` spawns `llama-server --jinja` per model on configured ports.
   - Auto-discovers the `llama-server` binary: explicit config → PATH → Homebrew → local build.
   - Polls `/v1/models` until the server is ready. Always stops servers on exit.
   - The `--jinja` flag is **required** for tool calling to work.

2. **Client Layer (`client.py`)**
   - `LlamaClient` is a thin wrapper around the official `openai` client for `/v1/chat/completions`.
   - Auto-injects a system message when tools are present but no system message exists in the conversation.
   - Exposes `last_payload` for debugging/logging.

3. **Schema + TestCase Layer (`schema_gen.py` + `dataset.py`)**
    - `tool` decorator: no-op marker for visually identifying tool functions.
    - `get_tool_schema()`: Uses `function-schema` library to convert Python function signatures (type hints + docstrings) into OpenAI-compatible tool JSON schemas.
    - `TestCase` class: Represents a single evaluation case. Tools are stored as schemas (dicts) for JSON serialization. `to_dict()` serializes to the JSON format expected by `dataset.json`.
    - `TestCaseBuilder`: Fluent builder for constructing `TestCase` objects with a chainable API.
    - Helper functions: `simple_test_case()`, `refusal_test_case()`, `parallel_test_case()` for common patterns.
    - `Dataset` class (`dataset.py`): Manages test cases with CRUD operations and JSON serialization.

4. **Evaluation Layer (`evaluator.py`)**
   - `Evaluator` compares model responses to ground truth with exact-match scoring.
   - Metrics: function name accuracy (set match), argument accuracy (exact JSON), hallucination (no extra tools), refusal correctness (no tool calls when expected).
   - A test **PASS** requires every metric to be exactly `1.0` — there is no fuzzy matching.
   - Extra argument keys are allowed but flagged as warnings.

## Data Flow

```
config.yaml (models)
      ↓
server_manager.py ──→ llama-server processes
                              ↓
dataset.json (tests) ──→ client.py ──→ HTTP POST /v1/chat/completions
                              ↓
                        evaluator.py ──→ metrics
                              ↓
                        results.json + results.md + logs/*.jsonl
```

## Key Files and Their Roles

| File | Role |
|------|------|
| `config.yaml` | Model registry: GGUF path, port, chat template, context size |
| `dataset.json` | Ground-truth test cases (prompts + expected tool calls) |
| `test_cases.py` | Tool definitions and test case objects (source of truth) |
| `dataset.py` | `Dataset` class for CRUD operations on `dataset.json` |
| `schema_gen.py` | `tool` decorator, `get_tool_schema()`, `TestCase`, `TestCaseBuilder` |
| `server_manager.py` | `LlamaServerManager` — spawns/kills llama-server |
| `client.py` | `LlamaClient` — raw HTTP to `/v1/chat/completions` |
| `evaluator.py` | `Evaluator` — exact-match scoring |
| `run_tests.py` | Orchestrator: runs all tests, writes JSON/Markdown/JSONL logs |
| `create_test_case.py` | Interactive CLI wizard for creating test cases |
| `debug_single.py` | Runs one test case against an already-running server |
| `gemma-3-tool-template.jinja` | Custom Jinja chat template for Gemma models |

## Adding New Test Cases

Define tools as annotated Python functions decorated with `@tool`, and `TestCase` objects in `test_cases.py`. This file serves as the source of truth.

### Using TestCaseBuilder (Recommended)

```python
from schema_gen import TestCaseBuilder, tool

@tool
def my_tool(name: str, count: int = 1) -> str:
    """Do something useful."""
    pass

test = (TestCaseBuilder()
    .id("my_test_01")
    .category("simple")
    .user_message("Run my_tool with name=foo and count=5")
    .add_tool(my_tool)
    .expect_tool_call(my_tool, name="foo", count=5)
    .build()
)
```

### Using Helper Functions

```python
from schema_gen import simple_test_case

test = simple_test_case(
    id="my_test_01",
    category="simple",
    question="What is the weather in Tokyo?",
    tool_callable=get_weather,
    expected_args={"city": "Tokyo", "unit": "celsius"},
)
```

### Serialize to dataset.json

Run `test_cases.py` to serialize all test cases:
```bash
python test_cases.py
```

Or use the `Dataset` class programmatically:
```python
from dataset import Dataset
from schema_gen import TestCaseBuilder

dataset = Dataset()
test = TestCaseBuilder().id("test_01").build()
dataset.add(test)
dataset.save()
```

Or use the interactive CLI wizard:
```bash
python create_test_case.py
```

## Important Behavior Notes

- **Exact-match evaluation:** The evaluator is strict. If the model includes an optional argument with a default value that differs from the expected dict, the case fails. Define `expected` precisely.
- **Chat templates are critical:** Use the correct `--chat-template` for the model family (`gemma`, `chatml`, `llama3`, etc.). Verify by curling `http://localhost:PORT/props` after startup.
- **Cannot use Ollama blobs:** GGUFs must be downloaded directly from HuggingFace.
- **System messages:** `client.py` auto-injects a default system message when tools are present but no system message exists. Test cases can override this via the `system_message` field.
- **Logs:** Every run writes a timestamped JSONL file to `logs/` containing the full request, response, and evaluation for each test case.
