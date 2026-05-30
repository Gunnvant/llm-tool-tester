import argparse
import importlib.util
import json
import os
import sys

from schema_gen import TestCase


def load_module(module_path: str):
    spec = importlib.util.spec_from_file_location("test_module", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_module"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser(description="Ingest TestCase objects from a Python module into dataset.json")
    parser.add_argument("module", help="Python file containing TestCase definitions")
    parser.add_argument("--dataset", default="dataset.json", help="Path to dataset.json")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing test IDs")
    args = parser.parse_args()

    mod = load_module(args.module)

    cases = []
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, TestCase):
            cases.append(obj)

    if not cases:
        print("No TestCase objects found in module.")
        return

    if os.path.exists(args.dataset):
        with open(args.dataset) as f:
            dataset = json.load(f)
    else:
        dataset = {"test_cases": []}

    existing_ids = {tc["id"] for tc in dataset["test_cases"]}
    added = 0
    skipped = 0

    for case in cases:
        case_dict = case.to_dict()
        if case.id in existing_ids:
            if args.overwrite:
                dataset["test_cases"] = [tc for tc in dataset["test_cases"] if tc["id"] != case.id]
                dataset["test_cases"].append(case_dict)
                print(f"Overwrote: {case.id}")
                added += 1
            else:
                print(f"Skipped (exists): {case.id}")
                skipped += 1
        else:
            dataset["test_cases"].append(case_dict)
            print(f"Added: {case.id}")
            added += 1

    with open(args.dataset, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"\nDone. Added: {added}, Skipped: {skipped}. Total: {len(dataset['test_cases'])}")


if __name__ == "__main__":
    main()
