# AGENTS.md

Compact instructions for OpenCode working in this repo. For full context see `CLAUDE.md`.

## What this repo is

A pure-Python framework that evaluates tool-calling capabilities of local LLMs served by `llama.cpp` (`llama-server`). It sends test prompts via raw HTTP to the OpenAI-compatible `/v1/chat/completions` endpoint and scores responses against ground-truth expectations.

## Essential commands

| Task | Command |
|------|---------|
| Full evaluation suite | `python run_tests.py --config config.yaml --dataset dataset.json --output results.json` |
| Run specific models only | `python run_tests.py --models qwen2.5-3b-it` |
| Debug one test (needs running server) | `python debug_single.py --model <name> --test-id <id>` |
| Add test cases from Python module | `python add_test_case.py my_cases.py` |
| Overwrite existing test IDs | `python add_test_case.py my_cases.py --overwrite` |
| Run all linters | `python -m ruff check . && python -m flake8 --config .flake8 . && python -m isort --check-only --diff .` |
| Auto-fix lint issues | `python -m ruff check . --fix && python -m isort . && python -m ruff format .` |

## Architecture (four thin layers)

1. **Server layer (`server_manager.py`)**
   - `LlamaServerManager` spawns `llama-server --jinja` per model on configured ports.
   - Auto-discovers binary: config override → `PATH` → Homebrew (`/opt/homebrew/bin/llama-server`) → local build (`./build/bin/llama-server`).
   - Polls `/v1/models` until ready. Always stops servers on exit.

2. **Client layer (`client.py`)**
   - `LlamaClient` is a thin `requests.post` wrapper to `/v1/chat/completions`.
   - Auto-injects a system message when tools are present but no system message exists in the conversation.
   - Exposes `last_payload` for debugging.

3. **Schema + TestCase layer (`schema_gen.py`)**
   - `tool` decorator: no-op marker for visually identifying tool functions.
   - `get_tool_schema()`: Uses `function-schema` to convert annotated Python functions into OpenAI-compatible tool JSON schemas.
   - `TestCase` class: Represents one evaluation case with live callables for tools. `to_dict()` serializes to the JSON format expected by `dataset.json`.

4. **Evaluation layer (`evaluator.py`)**
   - `Evaluator` compares model responses to ground truth with exact-match scoring.
   - Metrics: function name accuracy (set match), argument accuracy (exact JSON), hallucination (no extra tools), refusal correctness (no tool calls when expected).
   - A test **PASS** requires every metric to be exactly `1.0` — there is no fuzzy matching.
   - Extra argument keys are allowed but flagged as warnings.

## Critical gotchas

- **`--jinja` is required**: `llama-server` must be started with `--jinja` for tool calling to work. The framework always includes it.
- **Chat templates matter**: Use the correct `--chat-template` for the model family (`gemma`, `chatml`, `llama3`, etc.). Verify by curling `http://localhost:PORT/props` after startup.
- **Cannot use Ollama blobs**: GGUFs must be downloaded directly from HuggingFace. Ollama's internal blob files are incompatible with `llama.cpp`.
- **Exact-match evaluation**: If the model includes an optional argument with a default value that differs from the expected dict, the case fails. Define `expected` precisely.
- **System messages**: `client.py` auto-injects a default system message when tools are present but no system message exists. Test cases can override this via the `system_message` field.

## Linting & pre-commit

- **Pre-commit hook** (`.git/hooks/pre-commit`) runs on staged Python files: `isort` (auto-fix) → `ruff format` (auto-fix) → `ruff check` → `flake8`. If any gate fails, the commit is blocked. Formatters auto-fix and re-add files.
- **Config**: `pyproject.toml` (ruff, isort) and `.flake8`. Line length is **120**.

## Adding new test cases

Define tools as annotated Python functions decorated with `@tool`, and `TestCase` objects in a `.py` file, then ingest:

```bash
python add_test_case.py my_module.py
```

See `example_tools.py` for a concrete example.

## Output artifacts

Every run produces:
- `results.json` — full raw responses + per-metric scores.
- `results.md` — human-readable PASS/FAIL table.
- `logs/<model>_<timestamp>.jsonl` — one JSONL log per model with full request/response/evaluation for each test case.
