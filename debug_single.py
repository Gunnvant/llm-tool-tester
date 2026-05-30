"""Run a single test case against an already-running llama-server for quick debugging.

Usage:
    python debug_single.py --model gemma-3-1b-it --test-id simple_weather_01

This reads the model port from config.yaml and the test case from dataset.json,
sends exactly one request, and pretty-prints the request, response, and evaluation.
"""

import argparse
import json

import yaml

from client import LlamaClient
from evaluator import Evaluator


def main():
    parser = argparse.ArgumentParser(description="Debug a single test case against a running llama-server")
    parser.add_argument("--config", default="config.yaml", help="Model registry")
    parser.add_argument("--dataset", default="dataset.json", help="Test cases")
    parser.add_argument("--model", required=True, help="Model name from config")
    parser.add_argument("--test-id", required=True, help="Test case ID from dataset")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)
    with open(args.dataset) as f:
        dataset = json.load(f)

    model_cfg = config["models"][args.model]
    model_alias = model_cfg.get("model_alias", args.model)
    client = LlamaClient(f"http://localhost:{model_cfg['port']}", model_name=model_alias)

    test_case = None
    for tc in dataset["test_cases"]:
        if tc["id"] == args.test_id:
            test_case = tc
            break

    if test_case is None:
        raise ValueError(f"Test case '{args.test_id}' not found in {args.dataset}")

    print("=" * 60)
    print(f"Test: {test_case['id']} | Model: {args.model}")
    print("=" * 60)

    messages = test_case["messages"]
    if test_case.get("system_message"):
        messages = [{"role": "system", "content": test_case["system_message"]}] + list(messages)

    response = client.chat_completion(
        messages=messages,
        tools=test_case["tools"],
    )

    print("\n>>> REQUEST:")
    print(json.dumps(client.last_payload, indent=2))

    print("\n<<< RESPONSE:")
    print(json.dumps(response, indent=2))

    evaluator = Evaluator()
    result = evaluator.evaluate(test_case, response)

    print("\n>>> EVALUATION:")
    print(f"  Passed: {result['passed']}")
    print(f"  Metrics: {json.dumps(result.get('metrics', {}), indent=2)}")
    if "warnings" in result:
        print(f"  Warnings: {result['warnings']}")
    if "error" in result:
        print(f"  Error: {result['error']}")


if __name__ == "__main__":
    main()
