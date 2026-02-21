"""Evaluation harness for agent behavior scoring."""
from __future__ import annotations
import yaml
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class EvalResult:
    scenario_name: str
    agent: str
    score: float  # 0.0 to 1.0
    max_score: float
    details: list[str] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score else 0

def load_scenarios(path: str) -> list[dict]:
    """Load YAML evaluation scenarios."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("scenarios", [])

def score_rubric(output: dict, rubric: list[dict]) -> EvalResult:
    """Score an agent output against a rubric.

    Each rubric item has:
      - check: str description
      - field: str dotted path to check in output
      - condition: "exists" | "equals" | "contains" | "gt" | "lt" | "not_contains"
      - value: expected value (for equals/contains/gt/lt)
      - points: float
    """
    score = 0.0
    max_score = 0.0
    details = []

    for item in rubric:
        max_score += item["points"]
        field_val = _get_nested(output, item["field"])
        condition = item["condition"]
        expected = item.get("value")

        passed = False
        if condition == "exists":
            passed = field_val is not None
        elif condition == "equals":
            passed = field_val == expected
        elif condition == "contains":
            passed = expected in str(field_val).lower() if field_val else False
        elif condition == "not_contains":
            passed = expected not in str(field_val).lower() if field_val else True
        elif condition == "gt":
            passed = float(field_val) > float(expected) if field_val is not None else False
        elif condition == "lt":
            passed = float(field_val) < float(expected) if field_val is not None else False

        if passed:
            score += item["points"]
            details.append(f"  PASS: {item['check']} (+{item['points']})")
        else:
            details.append(f"  FAIL: {item['check']} (0/{item['points']}) — got {field_val}")

    return EvalResult(scenario_name="", agent="", score=score, max_score=max_score, details=details)

def _get_nested(d: dict, path: str):
    """Get a nested value from a dict using dot notation."""
    keys = path.split(".")
    val = d
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        elif isinstance(val, list) and k.isdigit():
            idx = int(k)
            val = val[idx] if idx < len(val) else None
        else:
            return None
    return val

def print_results(results: list[EvalResult]):
    """Pretty-print evaluation results."""
    total_score = sum(r.score for r in results)
    total_max = sum(r.max_score for r in results)

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    for r in results:
        status = "PASS" if r.score == r.max_score else "PARTIAL" if r.score > 0 else "FAIL"
        print(f"\n[{status}] {r.scenario_name} ({r.agent}): {r.score}/{r.max_score} ({r.pct:.0f}%)")
        for d in r.details:
            print(d)

    print(f"\n{'=' * 60}")
    pct = (total_score / total_max * 100) if total_max else 0
    print(f"TOTAL: {total_score}/{total_max} ({pct:.0f}%)")
    print("=" * 60)
