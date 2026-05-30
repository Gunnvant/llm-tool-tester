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

### Add test cases from a Python module to dataset.json
```bash
python add_test_case.py my_test_cases.py
# Overwrite existing IDs:
python add_test_case.py my_test_cases.py --overwrite
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
   - `LlamaClient` is a thin `requests.post` wrapper to `/v1/chat/completions`.
   - Auto-injects a system message when tools are present but no system message exists in the conversation.
   - Exposes `last_payload` for debugging/logging.

3. **Schema + TestCase Layer (`schema_gen.py`)**
   - `tool` decorator: no-op marker for visually identifying tool functions.
   - `get_tool_schema()`: Uses `function-schema` library to convert Python function signatures (type hints + docstrings) into OpenAI-compatible tool JSON schemas.
   - `TestCase` class: Represents a single evaluation case with live callables for tools. `to_dict()` serializes to the JSON format expected by `dataset.json`.

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
| `schema_gen.py` | `tool` decorator, `get_tool_schema()`, `TestCase` class |
| `server_manager.py` | `LlamaServerManager` — spawns/kills llama-server |
| `client.py` | `LlamaClient` — raw HTTP to `/v1/chat/completions` |
| `evaluator.py` | `Evaluator` — exact-match scoring |
| `run_tests.py` | Orchestrator: runs all tests, writes JSON/Markdown/JSONL logs |
| `add_test_case.py` | Ingests `TestCase` objects from Python modules into `dataset.json` |
| `debug_single.py` | Runs one test case against an already-running server |
| `example_tools.py` | Example tool definitions and sample `TestCase` objects |
| `gemma-3-tool-template.jinja` | Custom Jinja chat template for Gemma models |

## Adding New Test Cases

Define tools as annotated Python functions decorated with `@tool`, and `TestCase` objects in a `.py` file:

```python
from schema_gen import tool, TestCase

@tool
def my_tool(name: str, count: int = 1) -> str:
    """Do something useful."""
    pass

my_test = TestCase(
    id="my_test_01",
    category="simple",
    description="...",
    messages=[{"role": "user", "content": "Run my_tool with name=foo and count=5"}],
    tools=[my_tool],
    expected={
        "should_call_tools": True,
        "tool_calls": [
            {"name": "my_tool", "arguments": {"name": "foo", "count": 5}}
        ]
    },
)
```

Then ingest:
```bash
python add_test_case.py my_module.py
```

## Important Behavior Notes

- **Exact-match evaluation:** The evaluator is strict. If the model includes an optional argument with a default value that differs from the expected dict, the case fails. Define `expected` precisely.
- **Chat templates are critical:** Use the correct `--chat-template` for the model family (`gemma`, `chatml`, `llama3`, etc.). Verify by curling `http://localhost:PORT/props` after startup.
- **Cannot use Ollama blobs:** GGUFs must be downloaded directly from HuggingFace.
- **System messages:** `client.py` auto-injects a default system message when tools are present but no system message exists. Test cases can override this via the `system_message` field.
- **Logs:** Every run writes a timestamped JSONL file to `logs/` containing the full request, response, and evaluation for each test case.
