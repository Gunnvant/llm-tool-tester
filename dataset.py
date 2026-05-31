"""Dataset manager for test cases.

Provides CRUD operations for test cases and handles serialization
to/from dataset.json.
"""

import json

from schema_gen import TestCase


class Dataset:
    """Manages test cases with CRUD operations and JSON serialization."""

    def __init__(self):
        self.test_cases = []  # list of TestCase objects

    def save(self, path: str = "dataset.json") -> None:
        """Serialize all test cases to dataset.json using to_dict()."""
        data = {"test_cases": [tc.to_dict() for tc in self.test_cases]}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str = "dataset.json") -> None:
        """Load test cases from dataset.json."""
        with open(path) as f:
            data = json.load(f)

        self.test_cases = []
        for tc_dict in data["test_cases"]:
            # Reconstruct TestCase from dict
            # Tools are already schemas (dicts), so pass them directly
            tc = TestCase(
                id=tc_dict["id"],
                category=tc_dict["category"],
                description=tc_dict.get("description", ""),
                messages=tc_dict["messages"],
                tools=tc_dict["tools"],  # Schemas, not callables
                expected=tc_dict["expected"],
                evaluation_notes=tc_dict.get("evaluation_notes", ""),
                system_message=tc_dict.get("system_message", ""),
            )
            self.test_cases.append(tc)

    def add(self, test_case: TestCase, overwrite: bool = False) -> bool:
        """Add a test case. Returns True if added/overwritten."""
        existing_idx = None
        for i, tc in enumerate(self.test_cases):
            if tc.id == test_case.id:
                existing_idx = i
                break

        if existing_idx is not None:
            if overwrite:
                self.test_cases[existing_idx] = test_case
                return True
            return False

        self.test_cases.append(test_case)
        return True

    def remove(self, test_id: str) -> bool:
        """Remove a test case by ID. Returns True if removed."""
        for i, tc in enumerate(self.test_cases):
            if tc.id == test_id:
                self.test_cases.pop(i)
                return True
        return False

    def update(self, test_id: str, test_case: TestCase) -> bool:
        """Update an existing test case. Returns True if updated."""
        for i, tc in enumerate(self.test_cases):
            if tc.id == test_id:
                self.test_cases[i] = test_case
                return True
        return False

    def get(self, test_id: str) -> "TestCase | None":
        """Get a test case by ID. Returns None if not found."""
        for tc in self.test_cases:
            if tc.id == test_id:
                return tc
        return None

    def list(self, category: str = None) -> list[TestCase]:
        """List all test cases, optionally filtered by category."""
        if category:
            return [tc for tc in self.test_cases if tc.category == category]
        return self.test_cases.copy()

    def find(self, **kwargs) -> list:
        """Find test cases by attributes."""
        results = []
        for tc in self.test_cases:
            match = True
            for key, value in kwargs.items():
                if hasattr(tc, key):
                    if getattr(tc, key) != value:
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                results.append(tc)
        return results

    def __len__(self) -> int:
        return len(self.test_cases)

    def __repr__(self) -> str:
        return f"Dataset({len(self.test_cases)} test cases)"
