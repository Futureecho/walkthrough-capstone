"""Evaluate Quality Gate Agent behavior."""
from app.agents.quality_gate.tools import decide_quality
from tests.evaluation.eval_harness import EvalResult

def eval_quality_gate() -> list[EvalResult]:
    results = []

    # Scenario 1: Clear accept
    output = {"status": decide_quality(200, 128, 80, 100, 40, 50, 20)}
    r = EvalResult("Clear quality pass", "quality_gate", 0, 1)
    if output["status"] == "accepted":
        r.score = 1
        r.details.append("  PASS: Good image accepted")
    else:
        r.details.append(f"  FAIL: Expected accepted, got {output['status']}")
    results.append(r)

    # Scenario 2: Clear reject (very blurry)
    output = {"status": decide_quality(5, 128, 80, 100, 40, 50, 20)}
    r = EvalResult("Very blurry rejection", "quality_gate", 0, 1)
    if output["status"] == "rejected":
        r.score = 1
        r.details.append("  PASS: Blurry image rejected")
    else:
        r.details.append(f"  FAIL: Expected rejected, got {output['status']}")
    results.append(r)

    # Scenario 3: Borderline triggers LLM
    output = {"status": decide_quality(90, 45, 55, 100, 40, 50, 20)}
    r = EvalResult("Borderline triggers LLM", "quality_gate", 0, 1)
    if output["status"] == "borderline":
        r.score = 1
        r.details.append("  PASS: Borderline correctly identified")
    else:
        r.details.append(f"  FAIL: Expected borderline, got {output['status']}")
    results.append(r)

    # Scenario 4: Dark image rejected
    output = {"status": decide_quality(200, 10, 80, 100, 40, 50, 20)}
    r = EvalResult("Dark image rejection", "quality_gate", 0, 1)
    if output["status"] == "rejected":
        r.score = 1
        r.details.append("  PASS: Dark image rejected")
    else:
        r.details.append(f"  FAIL: Expected rejected, got {output['status']}")
    results.append(r)

    return results
