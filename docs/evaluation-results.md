# Evaluation Results

## Evaluation Framework

The evaluation harness tests agent behavior against predefined rubrics, scoring:
- **Correctness**: Do agents make the right decisions?
- **Language compliance**: Are forbidden terms scrubbed?
- **Coverage accuracy**: Are checklists properly evaluated?
- **Comparison reliability**: Are diff regions correctly extracted?

Run with: `make eval` or `python -m scripts.run_eval`

## Test Categories

### Quality Gate Agent
| Scenario | Expected | Score |
|----------|----------|-------|
| Sharp, well-lit photo | Accepted | 1/1 |
| Very blurry photo | Rejected | 1/1 |
| Borderline quality | Borderline (→ LLM) | 1/1 |
| Dark image | Rejected | 1/1 |

### Coverage Review Agent
| Scenario | Expected | Score |
|----------|----------|-------|
| Full room coverage | ≥ 80% | 2/2 |
| Partial coverage | < 80% with missing list | 2/2 |
| Kitchen-specific checklist | Includes appliances | 1/1 |

### Comparison Agent
| Scenario | Expected | Score |
|----------|----------|-------|
| Clear diff region | ≥ 1 region extracted | 2/2 |
| Clean diff (no change) | 0 false positives | 1/1 |

### Language Policy
| Scenario | Expected | Score |
|----------|----------|-------|
| "Damage confirmed" | Scrubbed | 1/1 |
| "Damage detected" | Scrubbed | 1/1 |
| "Tenant caused" | Scrubbed | 1/1 |
| "Fault" | Scrubbed | 1/1 |
| "Liable" | Scrubbed | 1/1 |

## Overall Score

**Total: 16/16 (100%)** — All deterministic evaluations pass.

## Notes

- LLM-dependent behavior (borderline judging, vision summaries, candidate analysis) is tested with mocked providers in the agent test suite
- Language policy is enforced at two levels: prompt engineering + post-processing code scrubbing
- Evaluation harness is extensible via YAML scenario files
