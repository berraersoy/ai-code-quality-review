"""
Ground truth loading and management module.

ACADEMIC PRINCIPLE:
Ground truth represents human-labeled defect benchmarks.
Under no circumstances should static analyzer or LLM predictions be automatically
promoted to ground truth, as doing so would invalidate experimental comparisons.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_GROUND_TRUTH_PATH = "evaluation_dataset/ground_truth.json"

REQUIRED_GROUND_TRUTH_FIELDS = {
    "id",
    "category",
    "line",
    "severity",
    "description"
}

VALID_CATEGORIES = {
    "security",
    "quality_style",
    "maintainability",
    "complexity",
    "performance"
}

VALID_SEVERITIES = {
    "low",
    "medium",
    "high"
}


def validate_ground_truth_item(item: Any) -> bool:
    """
    Validate structure and content of a ground truth item.
    """
    if not isinstance(item, dict):
        return False

    if not REQUIRED_GROUND_TRUTH_FIELDS.issubset(item.keys()):
        return False

    if not isinstance(item["id"], str) or not item["id"].strip():
        return False

    category = str(item["category"]).strip().lower()
    if category not in VALID_CATEGORIES:
        return False

    severity = str(item["severity"]).strip().lower()
    if severity not in VALID_SEVERITIES:
        return False

    if not isinstance(item["line"], int) or isinstance(item["line"], bool) or item["line"] < 1:
        return False

    if not isinstance(item["description"], str) or not item["description"].strip():
        return False

    return True


def load_ground_truth(file_path: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load ground truth dataset from a JSON file.

    Filters out metadata fields (starting with '_').
    Validates items and normalizes relative file paths.
    """
    if file_path is None:
        file_path = DEFAULT_GROUND_TRUTH_PATH

    path_obj = Path(file_path)
    if not path_obj.is_file():
        # Try finding relative to project root
        project_root = Path(__file__).resolve().parent.parent
        alt_path = project_root / file_path
        if alt_path.is_file():
            path_obj = alt_path
        else:
            raise FileNotFoundError(
                f"Ground truth dataset not found at '{file_path}'"
            )

    with open(path_obj, "r", encoding="utf-8") as file:
        data = json.load(file)

    dataset: Dict[str, List[Dict[str, Any]]] = {}

    for file_key, items in data.items():
        if file_key.startswith("_"):
            continue

        if not isinstance(items, list):
            continue

        valid_items = []
        for item in items:
            if validate_ground_truth_item(item):
                valid_items.append({
                    "id": str(item["id"]).strip(),
                    "category": str(item["category"]).strip().lower(),
                    "line": int(item["line"]),
                    "severity": str(item["severity"]).strip().lower(),
                    "description": str(item["description"]).strip()
                })

        dataset[file_key] = valid_items

    return dataset


def get_ground_truth_for_file(
    file_path: str,
    ground_truth_dataset: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve ground truth findings for a specific file.

    Handles matching by relative path, filename, or exact path.
    """
    if ground_truth_dataset is None:
        ground_truth_dataset = load_ground_truth()

    # Exact match
    if file_path in ground_truth_dataset:
        return ground_truth_dataset[file_path]

    # Normalized relative path match
    clean_path = str(Path(file_path)).replace("\\", "/")
    for key, items in ground_truth_dataset.items():
        clean_key = str(Path(key)).replace("\\", "/")
        if clean_key == clean_path:
            return items

    # Basename match fallback if unique
    file_name = Path(file_path).name
    matches = [
        items
        for key, items in ground_truth_dataset.items()
        if Path(key).name == file_name
    ]
    if len(matches) == 1:
        return matches[0]

    return []
