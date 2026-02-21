# Agent Design

## Design Principles

1. **Classical-first, LLM-second**: Use deterministic CV for measurable metrics; reserve LLM for subjective judgments
2. **Fail-closed**: When uncertain, request more information rather than making assumptions
3. **Cautious language**: Never confirm damage or assign fault — only identify "candidate differences"
4. **Tool-based architecture**: Each agent has explicit tools with clear input/output contracts
5. **Cost-efficient**: Minimize LLM calls through deterministic pre-filtering

## Agent 1: Quality Gate

**Purpose**: Ensure each captured photo is usable for documentation.

**Tools**:
| Tool | Type | Input | Output |
|------|------|-------|--------|
| `compute_blur_score` | Classical CV | image path | Laplacian variance (float) |
| `compute_darkness_score` | Classical CV | image path | Mean brightness 0-255 (float) |
| `compute_sharpness_score` | Classical CV | image path | Tenengrad variance (float) |
| `decide_quality` | Deterministic | scores + thresholds | accepted / rejected / borderline |

**Decision Boundaries**:
- Scores clearly above thresholds → **accepted** (no LLM needed)
- Scores clearly below (threshold - margin) → **rejected** (no LLM needed)
- Scores within margin → **borderline** → LLM vision judge decides

**LLM Judge Prompt**: Asks the model to evaluate if surfaces/fixtures are clearly visible despite borderline metrics.

## Agent 2: Coverage Review

**Purpose**: Ensure the room is fully documented from all required angles.

**Tools**:
| Tool | Type | Input | Output |
|------|------|-------|--------|
| `summarize_view` | Vision LLM | image + room type | JSON: visible surfaces, fixtures, coverage areas |
| `aggregate_coverage` | Deterministic | summaries + room checklist | coverage %, covered/missing areas |
| `next_best_shots` | LLM (text) | coverage state | Actionable photo instructions |

**Room Checklists**: Each room type has a required coverage checklist (walls, floor, ceiling, fixtures). Coverage % = checked items / total items.

**Fallback**: Without LLM, orientation hints from guided positions map to likely coverage areas.

## Agent 3: Comparison

**Purpose**: Identify candidate differences between move-in and move-out photos.

**Tools**:
| Tool | Type | Input | Output |
|------|------|-------|--------|
| `normalize_exposure` | Classical CV | two images | Histogram-equalized pair |
| `compute_structural_diff` | Classical CV (SSIM) | normalized pair | SSIM score + diff map |
| `extract_candidate_regions` | Classical CV | diff map | Bounding box regions |
| `analyze_candidate` | Vision LLM | cropped region pair | Confidence, reason codes, analysis |
| `compose_followup` | LLM (text) | analysis results | Neutral follow-up message |

**Language Policy Node**: Post-processes all text output to scrub forbidden terms:
- Forbidden: "damage confirmed", "damage detected", "tenant caused", "fault", "liable"
- Required hedging: "candidate difference", "possible", "appears to", "may indicate"

## State Management

Each agent uses a LangGraph `TypedDict` state that flows through the graph nodes. States are immutable between nodes — each node returns a partial update dict.

## Error Handling

- CV tool failures → log error, use zero scores (will trigger borderline/reject)
- LLM failures → fall back to deterministic behavior (accept borderline, use orientation hints)
- Missing images → skip pair, note in results
