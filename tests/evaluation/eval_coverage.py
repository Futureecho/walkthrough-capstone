"""Evaluate Coverage Review Agent behavior."""
from app.agents.coverage_review.tools import aggregate_coverage, get_checklist
from tests.evaluation.eval_harness import EvalResult

def eval_coverage() -> list[EvalResult]:
    results = []

    # Scenario 1: Full coverage
    summaries = [{"coverage_areas": get_checklist("Living Room"), "visible_surfaces": []}]
    output = aggregate_coverage(summaries, "Living Room")
    r = EvalResult("Full room coverage", "coverage_review", 0, 2)
    if output["coverage_pct"] >= 80:
        r.score += 1
        r.details.append("  PASS: Coverage >= 80%")
    else:
        r.details.append(f"  FAIL: Coverage {output['coverage_pct']}% < 80%")
    if len(output["missing"]) == 0:
        r.score += 1
        r.details.append("  PASS: No missing areas")
    else:
        r.details.append(f"  FAIL: Missing areas: {output['missing']}")
    results.append(r)

    # Scenario 2: Partial coverage
    summaries = [{"coverage_areas": ["wall-left", "floor"], "visible_surfaces": []}]
    output = aggregate_coverage(summaries, "Kitchen")
    r = EvalResult("Partial coverage detection", "coverage_review", 0, 2)
    if output["coverage_pct"] < 80:
        r.score += 1
        r.details.append("  PASS: Correctly identifies incomplete coverage")
    else:
        r.details.append(f"  FAIL: Should be < 80%, got {output['coverage_pct']}%")
    if len(output["missing"]) > 0:
        r.score += 1
        r.details.append(f"  PASS: Missing areas identified: {output['missing']}")
    else:
        r.details.append("  FAIL: Should have missing areas")
    results.append(r)

    # Scenario 3: Kitchen-specific checklist
    checklist = get_checklist("Kitchen")
    r = EvalResult("Kitchen checklist includes appliances", "coverage_review", 0, 1)
    if "appliances" in checklist or "countertop" in checklist:
        r.score = 1
        r.details.append("  PASS: Kitchen checklist has kitchen-specific items")
    else:
        r.details.append(f"  FAIL: Kitchen checklist missing kitchen items: {checklist}")
    results.append(r)

    return results
