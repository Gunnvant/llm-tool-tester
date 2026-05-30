import json


class Evaluator:
    """Compares model responses to ground-truth expectations."""

    def evaluate(self, test_case: dict, response: dict) -> dict:
        choice = response["choices"][0]
        message = choice["message"]
        actual_tool_calls = message.get("tool_calls") or []
        expected = test_case["expected"]

        result = {
            "test_id": test_case["id"],
            "passed": False,
            "metrics": {},
        }

        if expected["should_call_tools"]:
            self._evaluate_tool_call(test_case, actual_tool_calls, result)
        else:
            self._evaluate_refusal(test_case, actual_tool_calls, message, result)

        return result

    def _evaluate_tool_call(self, test_case, actual_tool_calls, result):
        expected = test_case["expected"]
        expected_calls = expected.get("tool_calls", [])

        if not actual_tool_calls:
            result["metrics"] = {
                "function_name_accuracy": 0.0,
                "argument_accuracy": 0.0,
                "hallucination": 0.0,
            }
            result["error"] = "Expected tool calls but model returned none"
            return

        # Build maps: name -> arguments dict
        expected_map = {}
        for tc in expected_calls:
            expected_map[tc["name"]] = tc["arguments"]

        actual_map = {}
        for tc in actual_tool_calls:
            func_block = tc.get("function", {})
            name = func_block.get("name")
            args_str = func_block.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}
            actual_map[name] = args

        expected_names = set(expected_map.keys())
        actual_names = set(actual_map.keys())

        # Function name accuracy: exact set match
        result["metrics"]["function_name_accuracy"] = 1.0 if expected_names == actual_names else 0.0

        # Hallucination: no extra tools beyond the expected set
        extra = actual_names - expected_names
        result["metrics"]["hallucination"] = 1.0 if not extra else 0.0

        # Argument accuracy: subset match for every expected call.
        # All expected keys/values must be present in actual args.
        # Extra keys are allowed but flagged as warnings.
        arg_scores = []
        warnings = []
        for name, expected_args in expected_map.items():
            if name not in actual_map:
                arg_scores.append(0.0)
                continue
            actual_args = actual_map[name]
            missing = [k for k in expected_args if k not in actual_args]
            mismatched = [k for k in expected_args if k in actual_args and actual_args[k] != expected_args[k]]
            extra = [k for k in actual_args if k not in expected_args]
            if missing or mismatched:
                arg_scores.append(0.0)
            else:
                arg_scores.append(1.0)
            if extra:
                warnings.append(f"tool '{name}' has extra keys: {extra}")

        result["metrics"]["argument_accuracy"] = sum(arg_scores) / len(arg_scores) if arg_scores else 0.0
        if warnings:
            result["warnings"] = warnings

        # Overall pass only if every metric is perfect
        result["passed"] = (
            result["metrics"]["function_name_accuracy"] == 1.0
            and result["metrics"]["argument_accuracy"] == 1.0
            and result["metrics"]["hallucination"] == 1.0
        )

        if not result["passed"] and "error" not in result:
            parts = []
            if result["metrics"]["function_name_accuracy"] != 1.0:
                parts.append("function name mismatch")
            if result["metrics"]["argument_accuracy"] != 1.0:
                parts.append("argument mismatch")
            if result["metrics"]["hallucination"] != 1.0:
                parts.append("hallucinated tools")
            result["error"] = "; ".join(parts)

    def _evaluate_refusal(self, test_case, actual_tool_calls, message, result):
        has_tool_calls = bool(actual_tool_calls)
        result["metrics"]["refusal_correctness"] = 0.0 if has_tool_calls else 1.0

        content = (message.get("content") or "").lower()
        keywords = test_case["expected"].get("content_must_contain", [])
        if keywords:
            result["metrics"]["content_keywords"] = any(k.lower() in content for k in keywords)
        else:
            result["metrics"]["content_keywords"] = None

        if has_tool_calls:
            result["passed"] = False
            result["error"] = "Model called tools when it should have refused"
        else:
            result["passed"] = True
