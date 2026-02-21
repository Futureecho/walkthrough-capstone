"""Evaluate language policy compliance."""
from app.agents.comparison.tools import apply_language_policy
from app.config import get_settings
from tests.evaluation.eval_harness import EvalResult

def eval_language_policy() -> list[EvalResult]:
    settings = get_settings()
    forbidden = settings.language_policy.forbidden
    hedging = settings.language_policy.required_hedging
    results = []

    test_texts = [
        "Damage confirmed in the kitchen area near the stove.",
        "Damage detected on the wall surface.",
        "Tenant caused this scratch on the floor.",
        "It is the tenant's fault that the window is cracked.",
        "The tenant is liable for the broken fixture.",
    ]

    for text in test_texts:
        cleaned = apply_language_policy(text, forbidden, hedging)
        r = EvalResult(f"Scrub: '{text[:40]}...'", "language_policy", 0, 1)
        violations = [f for f in forbidden if f.lower() in cleaned.lower()]
        if not violations:
            r.score = 1
            r.details.append("  PASS: All forbidden terms scrubbed")
        else:
            r.details.append(f"  FAIL: Remaining violations: {violations}")
        results.append(r)

    return results
