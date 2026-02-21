# Walkthrough Capture System

Dispute-friendly move-in/move-out property documentation with AI-powered quality assurance, coverage verification, and change detection.

## Architecture

```
Mobile Camera → FastAPI Backend → Three LangGraph Agents → HTML Report
                    ↕                      ↕
               SQLite DB            OpenAI GPT-4o / Claude
                    ↕
              WebSocket (real-time status)
```

**Three Agents** (each a LangGraph StateGraph):

1. **Quality Gate** — Classical CV (blur/darkness/sharpness) with LLM fallback for borderline cases
2. **Coverage Review** — Vision LLM summarizes each photo; deterministic checklist aggregation
3. **Comparison** — SSIM structural diff → region extraction → vision LLM analysis → language policy

See [docs/architecture.md](docs/architecture.md) and [docs/agent-design.md](docs/agent-design.md) for details.

## Quick Start

```bash
# Install dependencies
make install

# Seed demo data
make seed

# Start dev server
make dev

# Open http://localhost:8000
```

Set API keys in `.env`:
```
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

The system works without API keys (using deterministic fallbacks), but vision LLM features require at least one key.

## Usage

1. Open the app on your phone browser
2. Select a property → start a move-in or move-out session
3. Capture 8 guided photos per room (guided positions shown on screen)
4. Submit for review — quality gate and coverage run automatically
5. For move-out: comparison auto-runs against move-in photos
6. Tenant reviews candidate differences, confirms or disagrees
7. Generate HTML report with full audit trail

## Testing

```bash
# Run all tests
make test

# Run evaluation harness
make eval

# Lint
make lint
```

## Key Design Decisions

- **No video, no sphere UI** — Auto-stills with vision-LLM guided coverage
- **Deterministic 8-shot skeleton** — Agent fills gaps, not replaces human capture
- **Classical CV first** — LLM only for borderline/subjective decisions (cost-efficient)
- **Cautious language policy** — Never says "damage confirmed"; uses "candidate difference"
- **Fail-closed** — Uncertain → request close-up or mark "manual review recommended"

## Responsible AI

- No determinations of fault or liability
- Transparent confidence scores and reason codes
- Language policy enforced in prompts AND code
- Tenant response mechanism for every candidate
- Full audit trail with disclaimers

See [docs/responsible-ai.md](docs/responsible-ai.md).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.14 |
| Database | SQLite + SQLAlchemy (async) |
| Agents | LangGraph StateGraph |
| Vision LLM | OpenAI GPT-4o / Anthropic Claude |
| Classical CV | OpenCV + scikit-image (SSIM) |
| Frontend | Plain HTML/CSS/JS |
| Real-time | WebSockets |
| IDs | ULID |

## Limitations

- Photo comparison is sensitive to lighting and angle differences
- Not all visual changes indicate damage (wear, seasonal, lighting)
- System is advisory — human judgment required for final assessments
- Coverage accuracy depends on LLM vision quality
- Mobile browser camera API varies by device/OS
