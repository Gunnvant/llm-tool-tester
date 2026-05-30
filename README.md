# LLM Tool Tester

A pure-Python, zero-abstraction framework for testing tool-calling capabilities of local LLMs served by **llama.cpp** (`llama-server`).

## Philosophy

- **No wrappers**: Direct `openai` client to `llama-server`'s OpenAI-compatible `/v1/chat/completions` endpoint.
- **No heavy frameworks**: Just `openai`, `function-schema`, and `pyyaml`.
- **Transparent evaluation**: You control the GGUFs, the chat templates, and the test cases.

## Quick Start

### 1. Prerequisites

You need `llama-server` (from **llama.cpp**) installed and available on your system.

**Installation options:**

- **Homebrew (macOS):** `brew install llama.cpp`
- **Build from source:** Clone [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp), run `cmake -B build && cmake --build build`, then use `./build/bin/llama-server`.
- **Pre-built binaries:** Download from the [releases page](https://github.com/ggml-org/llama.cpp/releases).

The framework **auto-detects** the binary in this order:
1. `server_binary` override in `config.yaml`
2. `llama-server` on your `PATH`
3. `/opt/homebrew/bin/llama-server`
4. `/usr/local/bin/llama-server`
5. `./build/bin/llama-server` (relative to framework directory)
6. `../build/bin/llama-server`

If none are found, a clear error is printed telling you to install llama.cpp or set the full path in `config.yaml`.

### 2. Install dependencies

```bash
cd llm-tool-tester
uv sync
source .venv/bin/activate
```

> `uv` manages dependencies from `pyproject.toml` and produces a
> reproducible `uv.lock` file. After `uv sync`, activate the virtual
> environment (`.venv`) so you can run `python` commands directly.

### JupyterLab Debugging

A debug notebook lives in `notebooks/tool_calling_debug.ipynb` for interactively testing tool-calling request structures.

**One-time setup** (registers the project's venv as a Jupyter kernel):
```bash
source .venv/bin/activate
python -m ipykernel install --name llm-tool-tester --display-name "Python (llm-tool-tester)" --user
```

**Launch:**
```bash
jupyter lab notebooks/
```
Then select **"Python (llm-tool-tester)"** from the kernel picker (top-right).

### 3. Configure your models

Edit `config.yaml` and point each entry at a real GGUF file on disk.

> **Important**: `llama.cpp` **cannot** read Ollama's internal blob files. Download GGUFs directly from HuggingFace (e.g. `ggml-org/gemma-3-1b-it-GGUF`) and reference those.

Example `config.yaml`:

```yaml
models:
  gemma-3-1b-it:
    gguf_path: /Users/you/models/gemma-3-1b-it-Q4_K_M.gguf
    port: 8080
    chat_template: gemma
    context_size: 4096
```

### 4. Run the evaluation

```bash
python run_tests.py --config config.yaml --dataset dataset.json --output results.json
```

The script will:
1. Spawn `llama-server --jinja` for each model on its configured port.
2. Send every test case via raw HTTP.
3. Score responses against ground truth.
4. Write `results.json` and `results.md`.
5. **Kill** all server processes on exit.

### 5. Inspect results

- `results.json` — Full raw responses + per-metric scores.
- `results.md` — Human-readable table (PASS/FAIL, function/argument accuracy, hallucination, refusal).

## Adding / Removing Test Cases

### The easy way: Python definitions

Write a `.py` file with annotated functions and `TestCase` objects:

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

Then ingest it into `dataset.json`:

```bash
# Add new cases
python add_test_case.py my_test_cases.py

# Overwrite existing IDs
python add_test_case.py my_test_cases.py --overwrite
```

### The manual way: edit JSON

`dataset.json` is plain JSON. You can add, remove, or tweak test cases directly with any editor.

## Evaluation Metrics

| Metric | Meaning |
|---|---|
| **Function Name Accuracy** | Exact set match of tool names (order irrelevant). |
| **Argument Accuracy** | Exact JSON match of arguments. If a default needs changing, the model must change it. |
| **Hallucination** | `1.0` if the model only called tools that were in the prompt. |
| **Refusal Correctness** | For refusal cases, `1.0` if `tool_calls` is absent/empty. |

A test case is marked **PASS** only when every metric is `1.0`.

## Architecture

| File | Role |
|---|---|
| `config.yaml` | Model registry (GGUF path → port → chat template). |
| `dataset.json` | Ground-truth test cases (prompts + expected tool calls). |
| `schema_gen.py` | `function-schema` wrapper: Python functions → OpenAI `tools` JSON. |
| `server_manager.py` | Spawns/kills `llama-server --jinja` per model. |
| `client.py` | Raw HTTP client for `/v1/chat/completions`. |
| `evaluator.py` | Exact-match scorer with refusal detection. |
| `run_tests.py` | Orchestrator. Produces JSON + Markdown reports. |
| `add_test_case.py` | Ingests `TestCase` objects from Python modules into `dataset.json`. |

## Linting & Code Quality

The project uses `ruff`, `flake8`, and `isort` for code quality. A pre-commit hook runs all three on staged Python files.

### Running linters manually

```bash
# Check code with ruff
python -m ruff check .

# Auto-fix issues
python -m ruff check . --fix

# Format code
python -m ruff format .

# Check code with flake8
python -m flake8 --config .flake8 .

# Check import sorting
python -m isort --check-only --diff .

# Auto-fix import sorting
python -m isort .

# Run all checks at once
python -m ruff check . && python -m flake8 --config .flake8 . && python -m isort --check-only --diff .
```

### Pre-commit hook

The pre-commit hook at `.git/hooks/pre-commit` automatically runs `isort`, `ruff` (check + format check), and `flake8` on all staged Python files before allowing a commit. If any check fails, the commit is blocked until issues are resolved.

## Caveats

- **Tool calling requires `--jinja`**: `llama-server` must be started with the `--jinja` flag so the model's chat template can render tools correctly.
- **Chat templates matter**: Use the correct `--chat-template` for your model family (`gemma`, `chatml`, `llama3`, etc.). Check `http://localhost:PORT/props` after startup to verify.
- **Exact argument matching**: The evaluator is strict. Optional parameters that the user did not mention can still be included by the model; if they differ from the expected dict the case will be marked FAIL. Define your expected dict precisely.
