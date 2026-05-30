import argparse
import json
import os
from datetime import datetime

import yaml

from client import LlamaClient
from evaluator import Evaluator
from server_manager import LlamaServerManager


def generate_markdown(results: dict, dataset: dict, md_path: str):
    """Write a human-readable summary of evaluation results."""
    # Build quick lookup for category
    category_map = {tc["id"]: tc.get("category", "-") for tc in dataset["test_cases"]}

    lines = ["# Tool Calling Evaluation Results\n"]
    lines.append(f"Generated: {datetime.now().isoformat()}\n")

    for model_name, data in results.items():
        summary = data["summary"]
        lines.append(f"## Model: `{model_name}`")
        lines.append(f"- **Total Tests:** {summary['total']}")
        lines.append(f"- **Passed:** {summary['passed']}")
        lines.append(f"- **Failed:** {summary['failed']}")
        lines.append(f"- **Accuracy:** {summary['accuracy']:.2%}")
        lines.append("")
        lines.append("### Detailed Results")
        lines.append("")
        lines.append("| Test ID | Category | Passed | Function | Arguments | Hallucination / Refusal | Notes |")
        lines.append("|---|---|:---:|:---:|:---:|:---:|:---|")

        for r in data["results"]:
            tid = r["test_id"]
            cat = category_map.get(tid, "-")
            passed = "PASS" if r["passed"] else "FAIL"
            metrics = r.get("metrics", {})
            func = metrics.get("function_name_accuracy", "-")
            arg = metrics.get("argument_accuracy", "-")
            hall = metrics.get("hallucination", metrics.get("refusal_correctness", "-"))
            notes = r.get("error", "")
            lines.append(f"| {tid} | {cat} | {passed} | {func} | {arg} | {hall} | {notes} |")

        lines.append("")
        lines.append("---")
        lines.append("")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run tool-calling evaluation against llama-server instances")
    parser.add_argument("--config", default="config.yaml", help="Model registry")
    parser.add_argument("--dataset", default="dataset.json", help="Test cases")
    parser.add_argument("--output", default="results.json", help="Raw JSON results")
    parser.add_argument("--models", nargs="+", help="Specific models to test (default: all in config)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print request/response for every test case")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)
    with open(args.dataset) as f:
        dataset = json.load(f)

    models = args.models or list(config["models"].keys())
    evaluator = Evaluator()
    all_results: dict[str, dict] = {}

    os.makedirs("logs", exist_ok=True)

    manager = LlamaServerManager(args.config)
    try:
        for model_name in models:
            print(f"\n{'=' * 60}")
            print(f"Testing model: {model_name}")
            print(f"{'=' * 60}")

            manager.start(model_name)
            model_cfg = config["models"][model_name]
            # Use model_alias from config if available, otherwise model_name
            model_alias = model_cfg.get("model_alias", model_name)
            client = LlamaClient(f"http://localhost:{model_cfg['port']}", model_name=model_alias)

            log_path = os.path.join("logs", f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")

            model_results = []
            passed = 0
            failed = 0

            with open(log_path, "w") as log_file:
                for test_case in dataset["test_cases"]:
                    print(f"  [{test_case['id']}] ... ", end="", flush=True)

                    messages = test_case["messages"]
                    # Prepend explicit system_message from test case if present
                    if test_case.get("system_message"):
                        messages = [{"role": "system", "content": test_case["system_message"]}] + list(messages)

                    try:
                        response = client.chat_completion(
                            messages=messages,
                            tools=test_case["tools"],
                        )
                        result = evaluator.evaluate(test_case, response)
                        result["raw_response"] = response
                    except Exception as exc:
                        result = {
                            "test_id": test_case["id"],
                            "passed": False,
                            "error": str(exc),
                            "metrics": {},
                        }

                    request_payload = client.last_payload

                    if args.verbose:
                        print(f"\n  >>> REQUEST:\n{json.dumps(request_payload, indent=2)}")
                        print(f"  <<< RESPONSE:\n{json.dumps(response if 'raw_response' in result else {}, indent=2)}")

                    # Write JSONL log entry
                    log_entry = {
                        "test_id": test_case["id"],
                        "timestamp": datetime.now().isoformat(),
                        "request": request_payload,
                        "response": response if "raw_response" in result else None,
                        "evaluation": result,
                    }
                    log_file.write(json.dumps(log_entry) + "\n")
                    log_file.flush()

                    model_results.append(result)
                    if result["passed"]:
                        passed += 1
                        print("PASS")
                    else:
                        failed += 1
                        print(f"FAIL — {result.get('error', 'unknown')}")

            print(f"  [log] {log_path}")

            all_results[model_name] = {
                "summary": {
                    "total": len(dataset["test_cases"]),
                    "passed": passed,
                    "failed": failed,
                    "accuracy": passed / len(dataset["test_cases"]) if dataset["test_cases"] else 0.0,
                },
                "results": model_results,
            }

            manager.stop(model_name)
    finally:
        manager.stop_all()

    # Write JSON
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)

    # Write Markdown
    md_path = os.path.splitext(args.output)[0] + ".md"
    generate_markdown(all_results, dataset, md_path)

    print("\nResults saved:")
    print(f"  JSON  -> {args.output}")
    print(f"  Markdown -> {md_path}")


if __name__ == "__main__":
    main()
