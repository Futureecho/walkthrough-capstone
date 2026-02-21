"""Evaluate Comparison Agent behavior."""
import numpy as np
from app.agents.comparison.tools import apply_language_policy, extract_candidate_regions
from tests.evaluation.eval_harness import EvalResult

def eval_comparison() -> list[EvalResult]:
    results = []

    # Scenario 1: Region extraction from clear diff
    diff = np.zeros((200, 200), dtype=np.uint8)
    diff[50:100, 50:100] = 200
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    r = EvalResult("Extract regions from clear diff", "comparison", 0, 2)
    if len(regions) >= 1:
        r.score += 1
        r.details.append(f"  PASS: Found {len(regions)} region(s)")
    else:
        r.details.append("  FAIL: No regions found")
    if regions and regions[0]["w"] > 0 and regions[0]["h"] > 0:
        r.score += 1
        r.details.append("  PASS: Region has valid dimensions")
    else:
        r.details.append("  FAIL: Region dimensions invalid")
    results.append(r)

    # Scenario 2: No regions from clean diff
    clean = np.zeros((200, 200), dtype=np.uint8)
    regions = extract_candidate_regions(clean, threshold=0.1, min_area=100)
    r = EvalResult("No false positives from clean diff", "comparison", 0, 1)
    if len(regions) == 0:
        r.score = 1
        r.details.append("  PASS: No false positives")
    else:
        r.details.append(f"  FAIL: Found {len(regions)} false positive(s)")
    results.append(r)

    return results
