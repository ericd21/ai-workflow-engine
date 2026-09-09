# AI Workflow Engine

A state-driven AI workflow built with **LangGraph** and **FastAPI**. A contact form
submits a request; the engine runs it through a linear pipeline and returns a routing
decision, with a unique `run_id` and structured JSON logs for every run.

```
Intake → Extraction (LLM) → Triage (rules) → Routing (rules) → Logging → Response
```

- **Intake** — `IntakeRequest` (name, email/phone, department, message), validated by Pydantic.
- **Extraction** — an LLM classifies the message (department, tone, urgency, summary + confidences).
- **Triage** — deterministic rules reconcile the submitted vs. extracted department, assign
  priority, and flag runs for human review.
- **Routing** — deterministic rules pick a queue and an SLA.
- **Logging** — a single structured record per run (success *or* failure).

## Setup

```bash
poetry install
cp .env.example .env      # then edit
```

### Environment

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` (real API) or `mock` (offline, no key, no network) |
| `ANTHROPIC_API_KEY` | — | required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | |
| `LANGSMITH_TRACING` | `false` | `@traceable` steps are no-ops unless enabled |
| `LOG_TO_FILE` | `false` | also write rotating logs to `app.log` |
| `DEPARTMENT_CONFIDENCE_THRESHOLD` | `0.6` | min extraction confidence for the LLM to override the submitted department |

## Run

**Web app** (FastAPI backend + contact form):

```bash
poetry run poe dev            # uvicorn app.api.main:app --reload
# open http://localhost:8000/
```

Run it offline with no API key:

```bash
LLM_PROVIDER=mock poetry run poe dev
```

**CLI** (one workflow from the terminal):

```bash
poetry run workflow "The billing page shows the wrong amount" --department billing
LLM_PROVIDER=mock poetry run workflow "My printer is on fire" --department support
```

## Test

```bash
poetry run poe test          # pytest
poetry run pytest --cov=app
```

Tests never make live API calls — `LLM_PROVIDER=mock` and `call_llm` stubs cover the
LLM boundary.

## Project layout

```
app/
  api/         FastAPI app (routes, request/response models)
  config.py    .env loading + settings + run-id helper
  schemas/     Pydantic models (intake, extraction, triage, routing)
  llm/         LLM client, mock provider, extractor, prompts
  workflow/    LangGraph graph, engine wrapper, triage/routing rules, errors
  storage/     structured log-record assembly
  static/ templates/   contact form assets
```

See `docs/` for the full evaluation and implementation plan.
