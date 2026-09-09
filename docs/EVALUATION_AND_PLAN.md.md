# AI Workflow Engine — Evaluation, Error-Correction Plan, Test Plan, Backend Plan

> Status: evaluation + planning only. Nothing implemented. Pick up tomorrow.
> Plan-mode restriction meant this had to be written to the plan file
> (`C:\Users\edrit\.claude\plans\do-not-write-any-modular-harp.md`) rather than into the
> repo. First implementation step: copy this into the project as
> `docs/EVALUATION_AND_PLAN.md` (or similar).

---

## Context

The repo is an early-stage "AI workflow engine" demo: a contact form (`contact.html` +
`contact.js`) is meant to feed a LangGraph pipeline
(Intake → Extraction → Triage → Routing → Logging → Response) wrapped by a FastAPI
backend. Today the code does **not run** — multiple import-time and runtime errors — and
the FastAPI backend the frontend posts to **does not exist**. This document evaluates the
codebase, then lays out (2) an error-correction plan, (3) a test plan that needs no live
API calls, and (4) a plan for the missing backend and the full form→backend→engine
connection.

---

## Decisions log (all open questions resolved 2026-09-09)

- **Q1 — Department field.** Standardize the whole codebase on the name **`department`**
  and a **single `Department` enum**; delete the duplicate `Category` enum. Flow: form
  `department` → intake → LLM extraction may **override** it → ambiguity handled in
  `triage.py` (see Tier 0.5 for the rename, Tier 1 for the reconciliation rule). Resolves
  #19 and #30. Rationale: conceptually one field (override only makes sense if so), and the
  frontend already uses `department`, so no frontend change.

- **Q2 — Offline / no-API operation.** Add an **env-toggled mock LLM provider**.
  `app/config.py` reads `LLM_PROVIDER` (`anthropic` | `mock`, default `anthropic`).
  `call_llm` dispatches: `mock` → `app/llm/mock.py::generate_mock_response()` returns a
  canned valid extraction response (JSON block + trailing prose) with light keyword
  heuristics; `anthropic` → lazy-built `ChatAnthropic`. With `LLM_PROVIDER=mock` the app
  runs end-to-end with **no `ANTHROPIC_API_KEY` and zero network**. Tests use it for
  integration/API paths and still monkeypatch `call_llm` for retry/failure unit tests.

- **Q3 — Scope: comprehensive.** Fix runtime errors *and* project/packaging setup
  (Tier 4): `pyproject.toml` `packages` + valid scripts, `README.md`, `email-validator`,
  package strategy, `.env.example`. Rationale: broken `pyproject.toml` blocks
  `poetry install`, so the env can't be set up to run tests without it.

- **Q4 — Model ID.** Update to current Haiku, configurable. `ANTHROPIC_MODEL` env var,
  default **`claude-haiku-4-5`** (confirm exact current ID via `claude-api` reference at
  implementation time). `client.py` references the configured value everywhere — including
  the four hard-coded `"model": "claude-3-haiku-20240307"` strings in its log `extra=` dicts.

- **Q5 — Package strategy: real `__init__.py` files.** Remove `__init__.py` from
  `.gitignore:21`; add an empty `__init__.py` to `app/` and every Python subpackage
  (`schemas`, `llm`, `llm/prompts`, `workflow`, `storage`, plus new `api/`, `tests/`).
  Normalize all imports to the `app.` prefix.

- **Q6 — `app/main.py`: convert to a thin CLI** over `WorkflowEngine` — argparse:
  positional `message`, `--department` (default `other`), `--name` (default `"CLI User"`),
  `--email` (default `cli@example.com`) / `--phone` (since `IntakeRequest` requires
  `department`, `name`, and email-or-phone) → build `IntakeRequest` →
  `engine.run_workflow(intake)` → pretty-print. Delete the broken parallel `run_workflow`
  orchestrator (#21); `generate_run_id` moves to `app/config.py`. Backend is started
  **directly** via `uvicorn app.api.main:app` (no Python wrapper); add a `poe dev` / README
  shortcut. Test the CLI with one in-process `main()` + `capsys` test (+ optional CI smoke
  run); real coverage is the direct engine/API tests.

- **Q7 — LangSmith: keep `@traceable`** (no-op without `LANGSMITH_API_KEY`). Document
  `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` in `app/config.py` + `.env.example`; tests set
  `LANGSMITH_TRACING=false`.

- **Q8 — Error persistence: route node failures through `logging_node`.** Nodes catch →
  `state.errors.append(...)` → **return state, do not raise**. Conditional edges after
  `extraction` / `triage` / `routing`: `state.errors` non-empty → `logging`; else → next.
  `logging` → `response` always. `WorkflowEngine` inspects `final_state["errors"]`:
  non-empty → raise `WorkflowError(run_id, errors)` (new). API maps that to **502** with
  `detail` + `run_id`. Every failed run still produces a persisted `run_id`-tagged log
  record. Now required (Tier 1), not optional. (#17)

## PHASE 1 — Codebase evaluation

### 1.1 Structure

Poetry project, Python `^3.11`. Stack: LangGraph, LangChain (Anthropic), LangSmith,
FastAPI, Pydantic, python-dotenv, loguru, httpx.

```
app/
  main.py                     CLI-style orchestrator (broken; duplicates engine)
  logging_config.py           JSON logging setup
  schemas/
    intake.py                 IntakeRequest (+ Department enum)
    extraction.py             ExtractionResult (+ Category/Tone/Urgency enums)
    triage.py                 TriageDecision (+ Priority enum)
    routing.py                RoutingDecision (+ RoutingTarget/SLA enums)
  llm/
    client.py                 ChatAnthropic wrapper + retry (call_llm)
    extractor.py              LLM extraction step (run_extraction)
    prompts/extraction.py     EXTRACTION_PROMPT text
  workflow/
    graph.py                  LangGraph StateGraph (build_workflow_graph, workflow_graph)
    engine.py                 WorkflowEngine wrapper + singleton `engine`
    triage.py                 run_triage (deterministic rules)
    routing.py                run_routing (deterministic rules)
  storage/
    logging.py                write_log_record (final structured record)
  templates/contact.html      partial HTML fragment (no <!doctype>/<head>)
  static/js/contact.js        client-side validation + fetch POST /submit
  static/css/contact.css
scripts/create_structure.{ps1,sh}   scaffold; references many dirs that don't exist
pyproject.toml
.gitignore                     NOTE: globally ignores __init__.py
```

Missing entirely: `tests/`, `README.md`, any FastAPI app (`app/api/`), `.env`,
`__init__.py` files.

### 1.2 Data schemas

| Schema | Key fields |
|---|---|
| `IntakeRequest` (intake.py) | `name`, `email?` (EmailStr), `phone?`, `department` (enum), `message` (10–5000). Validator: email or phone required. |
| `ExtractionResult` (extraction.py) | `category`/`tone`/`urgency` enums + `*_confidence` floats [0,1], `summary` + confidence, `missing_info: list[str]`, `raw_model_output: str` |
| `TriageDecision` (triage.py) | `final_category`, `category_overridden`(+reason), `priority` enum, `human_review_required`(+reason), `missing_info`, copied confidences, `tone`/`urgency`/`summary`, `triage_notes` |
| `RoutingDecision` (routing.py) | `target` enum, `sla` enum, `human_review_required`(+reason), `final_category`, `urgency`, `priority` (typed `str` here — inconsistent), `summary`, `routing_notes` |
| `WorkflowState` (graph.py) | `run_id`, `intake`, `extraction?`, `triage?`, `routing?`, `logs?`, `errors: list`, `metadata: dict` |

### 1.3 Intended vs actual program flow

**Intended:** `contact.js` → `POST /submit` → FastAPI validates `IntakeRequest` →
`WorkflowEngine.run_workflow` → `workflow_graph.invoke` → nodes
intake→extraction→triage→routing→logging→response → return routing + `run_id` → JS renders
`run_id`.

**Actual:**
- Frontend posts to `/submit` — **no backend exists**, so it always errors.
- `engine.py` / `graph.py` are the "real" path but crash (see errors below).
- `main.py` is a **separate, broken** orchestrator that calls step functions by the wrong
  names/signatures and bypasses LangGraph entirely.
- The whole import chain requires a live `ANTHROPIC_API_KEY` because `client.py` builds
  `ChatAnthropic` at module import.

### 1.4 Errors found

#### A. Import-time — nothing runs until fixed

1. **`app/schemas/intake.py:1,24`** — `root_validator` (Pydantic v1 API). Deps pin
   `pydantic = "*"` → v2, where bare `@root_validator` raises `PydanticUserError` at class
   definition. → fix: `@model_validator(mode="after")`.
2. **`app/schemas/intake.py:1`** — `EmailStr` needs `email-validator`, **not in
   `pyproject.toml`**. `ImportError` on first import.
3. **`app/llm/extractor.py:4,73`** — imports/annotates `IntakePayload`; the class is
   `IntakeRequest`. `ImportError`.
4. **`app/llm/client.py:12-17`** — `ChatAnthropic(...)` instantiated at **module import**
   with `api_key=os.getenv(...)`. Unset key → construction error → importing `client` (and
   everything downstream: extractor, graph, engine) fails. Also nothing loads `.env`
   (`python-dotenv` unused).
5. **`app/main.py:5-8`** — broken imports:
   - `from llm.extractor import extract_structured_payload` — missing `app.` prefix
     (only resolves if CWD is `app/`), and no such function (`run_extraction`).
   - `from workflow.triage import triage` — actual: `run_triage`.
   - `from workflow.routing import route` — actual: `run_routing`.
   - `from app.logging_config import configure_logging` — uses `app.` prefix, unlike the
     two lines above. Import style is inconsistent across the file/codebase.

#### B. Runtime NameError / TypeError — crash when the graph runs

6. **`app/workflow/graph.py:51`** — `triage_node` calls undefined `run_triage_rules`
   (import is `run_triage`). `NameError`.
7. **`app/workflow/graph.py:61`** — `routing_node` calls undefined `run_routing_rules`
   (import is `run_routing`). `NameError`.
8. **`app/workflow/engine.py:27`** — `generate_run_id()` not imported/defined here (lives
   in `main.py`). `NameError`. (`uuid` imported at `engine.py:2`, unused. Inline comment
   flags this.)
9. **`app/workflow/engine.py:35-38`** — `initial_state = {"run_id": str, "intake": intake}`
   passes the `str` **type object**, not a value. `WorkflowState` validation fails.
10. **`app/workflow/engine.py:48`** — `return final_state.routing`. `graph.invoke()`
    returns a dict-like value map, not an attribute object → `AttributeError`. Should be
    `final_state["routing"]` (verify against installed langgraph version).
11. **`app/llm/extractor.py:104`** — `_parse_extraction_json(parsed)` called with 1 arg;
    signature is `_parse_extraction_json(raw_output, run_id)` (`:17`). `TypeError`.

#### C. Logging subsystem — structured fields silently dropped

12. **`app/logging_config.py:16-17`** — `JsonFormatter.format` reads `record.extra`, which
    stdlib `logging` never sets (the `extra=` dict is flattened onto the record as
    individual attributes). Result: **every** structured field (`run_id`, `event`, …) the
    codebase logs is discarded. → fix: merge `record.__dict__` minus the reserved
    `LogRecord` keys.
13. **`app/logging_config.py:33-35`** — `configure_logging` adds a `StreamHandler` on every
    call → duplicate log lines if called more than once. → guard / clear handlers.
14. **Consequence once #12 fixed:** `app/storage/logging.py:42-48` logs
    `extra={"summary": record}` where `record` holds enum objects (from `model_dump()`
    without `mode="json"`) and is nested → `json.dumps` in the formatter raises
    `TypeError: not JSON serializable`. Same latent bug in `app/main.py:47-53`. → use
    `model_dump(mode="json")` and `json.dumps(..., default=str)`.

#### D. Logic / robustness — non-fatal but wrong

15. **`app/llm/extractor.py:29-36`** — JSON slice uses `raw_output.find("}")` (first
    closing brace, not matched/last). Works only because the schema JSON is flat. Also
    `json_end = find("}") + 1` → `-1 + 1 = 0` when absent, so the guard `json_end == -1`
    (`:32`) is dead. → use `rfind`/balanced scan/regex and fix the sentinel.
16. **`app/llm/extractor.py`** — no explicit check that `category`/`tone`/`urgency` strings
    are within the allowed enum sets before constructing `ExtractionResult` (raw
    `ValidationError` surfaces in the retry loop). Minor.
17. **`app/workflow/graph.py` nodes** — each node does `state.errors.append(str(e)); raise`.
    Raising aborts the LangGraph run, so `logging_node` never records the failure and the
    appended error is lost. If partial logging on failure is wanted, need a conditional
    error edge to the logging node.
18. **`app/schemas/routing.py:45`** — `priority: str` while `TriageDecision.priority` is
    `Priority` enum and `run_routing` passes it through. Works (str-enum) but inconsistent.
    → `priority: Priority`.
19. **`intake.py:6-10` vs `extraction.py:5-9`** — `Department` and `Category` are duplicate
    identical enums. Not a bug; consolidation opportunity.
20. **`app/workflow/triage.py:33,68`** — override/human-review rules key on literal
    `"error_code"` / `"order_number"` tokens in `missing_info`; nothing guarantees the
    extractor ever produces those exact strings, so the rules are effectively dead. Design
    note.
21. **`app/main.py:18-73`** — `run_workflow` is a second, independent orchestrator that
    bypasses the engine and calls step functions with wrong names/signatures. Duplicate
    source of truth. → make `main.py` a thin CLI over `WorkflowEngine`, or delete it.
22. **`pyproject.toml`** — setup blockers:
    - No `packages` entry; package name `ai_workflow_engine` ≠ `app/` folder →
      `poetry install` fails ("No file/folder found for package").
    - `readme = "README.md"` but no `README.md` → install fails.
    - `[tool.poetry.scripts]` values (`dev = "uvicorn app.api.main:app --reload"`, …) are
      **not** valid console-script specs (must be `pkg.module:callable`), and
      `app.api.main:app` doesn't exist.
    - `email-validator` missing (see #2).
23. **`.gitignore:21`** — `__init__.py` globally ignored. With none present, `app` only
    works as a PEP-420 namespace package and only when invoked correctly
    (`python -m app.main` from repo root). Fragile; combined with #5's bare imports it's
    inconsistent. → decide package strategy.
24. **`app/templates/contact.html`** — not a full document (no `<!doctype>`, `<html>`,
    `<head>`; `<link>`/`<script>` inside `<header>` in the body). Browsers cope, but should
    be wrapped and needs a backend to serve it.
25. **`app/static/js/contact.js:78,88-98`** — posts to `/submit`, expects `data.run_id` on
    success and `data.detail` on error (FastAPI default error shape). Backend must honor
    this contract.
26. **`loguru`** — dependency, unused (stdlib `logging` used throughout). Adopt or drop.
27. **`app/workflow/graph.py:2`** — `END` imported, unused. `langsmith.traceable` used in
    several modules; inert without `LANGSMITH_API_KEY` (fine, worth a config note).

#### E. Frontend ↔ engine gap (Phase 4)

28. **No FastAPI app exists.** `app/api/` not created; `main.py` is a CLI, not ASGI.
    Nothing serves `contact.html` or `/static`, nothing handles `/submit`.
29. **`WorkflowEngine.run_workflow` never returns `run_id`** (generated at `engine.py:27`,
    lost). Frontend needs it. Contract mismatch.
30. **`department` is dropped** — never put into state or passed to `run_triage`, despite
    `TriageDecision.category_overridden` ("Whether the dropdown was overridden").

---

## PHASE 2 — Error-correction plan (prioritized by blast radius)

### Tier 0 — unblock import (everything is dead until these land)

- **`app/schemas/intake.py`**: `root_validator` → `model_validator(mode="after")`; keep
  the email-or-phone rule. (#1)
- **`pyproject.toml`**: add `email-validator` via `pydantic[email]` — or drop `EmailStr`
  for `str` + regex if we want zero new deps. (#2)
- **`app/llm/extractor.py`**: `IntakePayload` → `IntakeRequest` (import + annotation). (#3)
- **`app/llm/client.py`**: lazy/cached `ChatAnthropic` (`get_client()` singleton). Add a
  central `.env` load via new `app/config.py` (`python-dotenv`). `call_llm` dispatches on
  `LLM_PROVIDER`: `mock` → `app/llm/mock.py::generate_mock_response(prompt)` (new);
  `anthropic` → lazy client. `ChatAnthropic` is never constructed in mock mode. (#4, Q2)
- **Package strategy** (Q5, resolved): real packages — remove `__init__.py` from
  `.gitignore:21`, add an empty `__init__.py` to `app/` and every subpackage (`schemas`,
  `llm`, `llm/prompts`, `workflow`, `storage`, plus new `api/`, `tests/`). Normalize **all**
  imports to the `app.` prefix (fixes `main.py:5-7`). (#5, #23)

### Tier 0.5 — `category` → `department` rename (one atomic refactor, before Tier 1)

Do this first so the Phase 2 fixes land on consistent names instead of being rewritten.

- **One enum:** keep `Department` (move to `app/schemas/common.py` or keep in `intake.py`),
  import everywhere, **delete `Category`** from `extraction.py`. (#19)
- **Rename identifiers:**
  - `extraction.py`: `category` → `department`, `category_confidence` → `department_confidence`
  - `triage.py` (schema + `run_triage` logic): `final_category` → `final_department`,
    `category_overridden` → `department_overridden`,
    `category_override_reason` → `department_override_reason`,
    `category_confidence` → `department_confidence`, locals `extracted_category` → `extracted_department`
  - `routing.py` (schema + `run_routing`): `final_category` → `final_department`
- **LLM contract in lockstep** (or extraction breaks): `app/llm/prompts/extraction.py`
  field list + JSON schema block; `extractor.py` `required_fields` set,
  `_parse_extraction_json` keys, and the `ExtractionResult(...)` constructor.
- **Leave `RoutingTarget` values** (`support_queue`, …) unchanged — queue ids, not the field.
- **Frontend:** no change — already `department`.

### Tier 1 — engine execution path

- **`app/workflow/graph.py`**: `run_triage_rules` → `run_triage`; `run_routing_rules` →
  `run_routing`. (#6, #7)
- **`app/workflow/graph.py` — error routing (Q8):** nodes catch → `state.errors.append(...)`
  → return state (no `raise`). `add_conditional_edges` after `extraction`/`triage`/`routing`:
  errors present → `logging`, else → next. `logging` → `response` always. Uses `END`
  (currently imported unused). (#17, #27)
- **`app/config.py`** (new): `generate_run_id()` (uuid4 str) — imported by `engine.py` and
  `main.py`. (#8)
- **`app/workflow/engine.py`**: import `generate_run_id`; build `initial_state` with the
  real `run_id` string; return `{"run_id": run_id, "routing": final_state["routing"]}`
  (verify langgraph return shape); if `final_state["errors"]` non-empty raise
  `WorkflowError(run_id, errors)` (new, in `app/workflow/`); drop unused `uuid`.
  (#8, #9, #10, #29, Q8)
- **`app/llm/extractor.py`**: pass `run_id` into `_parse_extraction_json`; robust JSON
  slice (`rfind`/regex) + fix the `-1` sentinel. (#11, #15)
- **`app/workflow/triage.py` — department reconciliation (Q1):** `run_triage` gains a
  `submitted_department: Department` param (passed from `state.intake.department`). Rule:
  - LLM `department` == submitted → `final_department` = that, `department_overridden=False`.
  - They differ **and** `extraction.department_confidence >= 0.6` → `final_department` = LLM
    value, `department_overridden=True`, `department_override_reason` set.
  - They differ **and** confidence `< 0.6` → keep `submitted_department` as
    `final_department`, `human_review_required=True`,
    `human_review_reason="ambiguous department"` (this is the "ambiguity addressed in
    triage" path). Threshold in `app/config.py`.
  Update `graph.py:triage_node` to pass the arg; keep `run_routing` consuming
  `final_department`. (#30)

### Tier 2 — logging correctness

- **`app/logging_config.py`**: rewrite `JsonFormatter.format` to merge non-standard
  `LogRecord` attributes (diff against a reserved-key set); `json.dumps(..., default=str)`.
  Guard `configure_logging` against duplicate handlers. (#12, #13)
- **`app/storage/logging.py`** + **`app/main.py`**: `model_dump(mode="json")` for logged
  payloads. (#14)

### Tier 3 — consistency / dead code / design

- **`app/main.py`** (Q6, resolved): thin CLI over `WorkflowEngine` — argparse message arg →
  `IntakeRequest` → `engine.run_workflow` → print. Delete the broken parallel orchestrator;
  `generate_run_id` moves to `app/config.py`. (#21)
- **`app/schemas/routing.py`**: `priority: str` → `Priority`. (#18)
- ~~Consolidate `Department`/`Category`~~ — done in **Tier 0.5**. (#19, #30)
- Decide whether the `error_code`/`order_number` missing-info tokens should be real
  (minor; deferrable). (#20)
- ~~Optional: conditional error edge~~ — now required, moved to Tier 1 (Q8). (#17)
- Clean unused imports (`uuid` in `engine.py`); drop `loguru` from deps (unused). (#26, #27)
- Wrap `contact.html` in a full document, move `<link>`/`<script>` into `<head>`. (#24)

### Tier 4 — packaging / setup

- **`pyproject.toml`**: `packages = [{include = "app"}]`; create `README.md`; replace the
  invalid `[tool.poetry.scripts]` — use `[tool.poe.tasks]` (poethepoet):
  `dev = "uvicorn app.api.main:app --reload"`, `test = "pytest"`, `lint`, `typecheck`;
  add `pytest`, `pytest-asyncio`, `pytest-cov`, `poethepoet`; add `email-validator`. (#22)
- Add `.env.example`. (#4)

---

## PHASE 3 — Test plan (no live API calls)

### Infrastructure

- `tests/` + `conftest.py`. Add `pytest`, `pytest-asyncio` (`pytest-mock` optional).
  `[tool.pytest.ini_options]` in `pyproject.toml`.
- **Central mock:** monkeypatch `app.llm.client.call_llm` (or the lazy `get_client`) to
  return canned raw strings — valid extraction JSON + trailing prose. Provide variants:
  high-confidence, low-confidence, malformed-then-valid (retry).
- `LLM_PROVIDER=mock` (session/env fixture) drives the graph/engine/API integration tests
  with no network; unit tests of the retry loop still monkeypatch `call_llm` to inject
  malformed output / exceptions.
- Test env: dummy `ANTHROPIC_API_KEY`, `LANGSMITH_TRACING=false` so imports/`@traceable`
  are inert.

### Unit tests

| Target | Cases |
|---|---|
| `schemas/intake.py` | valid; email-only ok; phone-only ok; neither → error; name/message length bounds; bad department rejected |
| `schemas/extraction/triage/routing` | confidence `ge/le` bounds; enum coercion; required fields |
| `extractor._parse_extraction_json` | JSON + prose; trailing/nested brace; missing-field detection; no JSON → ValueError; malformed → ValueError |
| `extractor.run_extraction` (mock `call_llm`) | happy path → `ExtractionResult`; malformed-then-valid exercises retry; always-malformed → `RuntimeError` after 3; `raw_model_output` retained |
| `llm/client.call_llm` (mock `.invoke`) | success; one fail then success; all fail → `RuntimeError`; retry/latency logged |
| `workflow/triage.run_triage` | department reconciliation (match / override / ambiguous — see Q1 rule); priority high/medium/low mapping; department_confidence < 0.55 → human review; summary_confidence < 0.50 → human review; `"order_number"` missing → human review |
| `workflow/routing.run_routing` | human_review → human_review_queue + one_hour SLA; category→queue map; urgency→SLA map; priority/summary passthrough |
| `storage/logging.write_log_record` | dict with all sections; handles pydantic and plain dict; enum-safe serialization |
| `logging_config.JsonFormatter` | record logged with `extra={...}` actually emits those keys; non-serializable → str fallback; no duplicate handlers |

### Integration tests (still no network)

- `workflow/graph.py`: compile graph, invoke with mocked `call_llm`; assert
  `extraction`/`triage`/`routing`/`logs` populated and mutually consistent; assert node
  order via captured log events.
- `workflow/engine.WorkflowEngine.run_workflow`: mocked `call_llm` → returns `run_id` +
  routing; `run_id` is a UUID; two calls → distinct ids.
- Failure propagation (Q8): mocked `call_llm` raising → graph routes to `logging` →
  `state.errors` populated, `state.logs` still written with the partial record →
  `run_workflow` raises `WorkflowError` carrying `run_id` + errors.
- Department reconciliation (Q1): three cases — match; differ + high confidence → override
  (`department_overridden=True`, LLM value wins); differ + low confidence → keep submitted
  value + `human_review_required=True`.

### API tests (Phase 4 code, no network)

- `TestClient`: `GET /` serves the page; `GET /static/...` serves assets; `GET /health`.
- `POST /submit` happy path (mock engine or `call_llm`) → 200 + `{run_id, ...}` matching
  `contact.js`.
- `POST /submit` validation failures → 422 with `detail` (neither email nor phone; short
  message; missing department).
- `POST /submit` engine raises `WorkflowError` → 502 with `{detail, run_id}` (so
  `contact.js` `showError` works).
- Payload round-trip: JS shape (`email: null`) deserializes into `IntakeRequest`.

Also add a unit test for `app/llm/mock.py::generate_mock_response` — output parses as valid
extraction JSON and satisfies `ExtractionResult`.

**Coverage target:** all of `schemas/`, `llm/`, `workflow/`, `storage/`, `logging_config`,
plus new `api/`. No network: `LLM_PROVIDER=mock` for integration paths, `ChatAnthropic` only
exercised via a mocked `.invoke` in `client.py` unit tests.
**Run:** `poetry run pytest` (`--cov=app` once `pytest-cov` added).

---

## PHASE 4 — FastAPI backend + form → backend → engine connection

### New module: `app/api/main.py` (+ `app/api/__init__.py`)

**1. App setup**
- `app = FastAPI(title="AI Workflow Engine")`.
- Startup: `configure_logging()`, load `.env` (via `app/config.py`).
- `app.mount("/static", StaticFiles(directory="app/static"), name="static")`.
- Jinja2 `Jinja2Templates("app/templates")` **or** serve `contact.html` as a static file.
  Requires the Tier 3 fix wrapping `contact.html` in a full document.

**2. Routes**
- `GET /` → render/return `contact.html`.
- `GET /health` → `{"status": "ok"}` (no engine touch) — for liveness/tests.
- `POST /submit`:
  - Body model = `IntakeRequest` → FastAPI auto-validates (422 + `detail` on failure,
    matches `contact.js`).
  - Run the sync workflow off the event loop:
    `await run_in_threadpool(engine.run_workflow, intake)`.
  - Response model `SubmitResponse`:
    `{ run_id, target, sla, final_department, priority, human_review_required, summary }`.
    `contact.js` needs only `run_id` today; returning routing makes the demo meaningful.
  - Errors: catch `WorkflowError` (and any unexpected exception) →
    `JSONResponse(status_code=502, {"detail": "...", "run_id": <id if known>})` so
    `contact.js`'s `throw new Error(data.detail)` path works. The failed run already has a
    persisted structured log record (Q8). Log with `run_id`.

**3. Engine changes required for the connection**
- `WorkflowEngine.run_workflow` must **return `run_id`** (Tier 1 / #29).
- Fix `initial_state` + step-function names (Tier 1) or the first real request 500s.
- `department` handling (Q1, resolved): thread `intake.department` into `run_triage` (new
  `submitted_department` param); reconciliation rule (match / override / ambiguous) lives in
  Tier 1 triage bullet.
- Add `WorkflowError(run_id, errors)` and raise it from `run_workflow` when
  `final_state["errors"]` is non-empty (Q8).
- Optionally accept a client-supplied `run_id` for idempotency/tracing (align
  `engine.py` with `main.py`'s `run_id: str | None` signature).

**4. End-to-end data flow**
```
contact.html form
  → contact.js: client-side validation; JSON {name, email|null, phone|null, department, message}
  → fetch POST /submit (application/json)
  → FastAPI validates body as IntakeRequest (422 on bad input)
  → run_in_threadpool(engine.run_workflow, intake)
      → WorkflowEngine: generate run_id, build WorkflowState
      → workflow_graph.invoke(state)
          intake → extraction (run_extraction → call_llm → mock provider when LLM_PROVIDER=mock)
          → triage (run_triage, gets intake.department) → routing (run_routing)
          → logging (write_log_record) → response
          [any node error → append to state.errors, skip ahead to logging → response]
      → if state.errors: raise WorkflowError(run_id, errors); else return {run_id, routing}
  → success: FastAPI builds SubmitResponse {run_id, target, sla, final_department, ...} → 200
  → failure: 502 {detail, run_id}  (structured log record already persisted)
  → contact.js renders run_id (success) or showError(detail) (failure)
```

**5. Config (`app/config.py`, new)**
- `python-dotenv` load; settings: `LLM_PROVIDER` (`anthropic|mock`, default `anthropic`),
  `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `LANGSMITH_*`, `LOG_TO_FILE`.
- Consumed by `client.py` (provider dispatch + lazy client), `logging_config.py`,
  `api/main.py`.
- New `app/llm/mock.py::generate_mock_response(prompt) -> str` — canned valid extraction
  response (JSON + trailing prose); light keyword heuristics for `department` / `urgency` /
  `tone` so the demo isn't static.
- Commit `.env.example` (`LLM_PROVIDER=anthropic`, `ANTHROPIC_MODEL=claude-haiku-4-5`);
  `.env` already gitignored.

**6. Run / verify**
- `poetry run uvicorn app.api.main:app --reload` → `http://localhost:8000/`.
- Submit with a real key → `run_id` + routing outcome; confirm stdout JSON logs carry
  `run_id` / `event`.
- Without a key: `LLM_PROVIDER=mock` → full round trip, no API call.
- `poetry run pytest` green.
- Fix or document the uvicorn command in `pyproject.toml` (#22).

---

## Open questions (need your answers before implementation)

1. ~~**Department dropdown**~~ — **RESOLVED 2026-09-09:** rename `category` → `department`
   everywhere, single `Department` enum, LLM may override the form value, ambiguity handled
   in `triage.py`. See Decisions log + Tier 0.5.
2. ~~**Offline / no-API operation**~~ — **RESOLVED 2026-09-09:** mock LLM provider
   (`LLM_PROVIDER=mock`) + `app/llm/mock.py`. See Decisions log + Tier 0 client bullet +
   Phase 4 config.
3. ~~**Scope**~~ — **RESOLVED 2026-09-09:** comprehensive (Tier 4 included). See Decisions log.
4. ~~**Model ID**~~ — **RESOLVED 2026-09-09:** `ANTHROPIC_MODEL` env, default
   `claude-haiku-4-5`. See Decisions log.
5. ~~**Package strategy**~~ — **RESOLVED 2026-09-09:** real `__init__.py` files, un-ignore
   in `.gitignore`. See Decisions log + Tier 0.
6. ~~**`app/main.py`**~~ — **RESOLVED 2026-09-09:** convert to a thin CLI over
   `WorkflowEngine`; backend started directly via uvicorn. See Decisions log.
7. ~~**LangSmith**~~ — **RESOLVED 2026-09-09:** keep `@traceable`; document env vars. See
   Decisions log.
8. ~~**Error persistence**~~ — **RESOLVED 2026-09-09:** route node failures through
   `logging_node` (conditional edges), engine raises `WorkflowError`, API returns 502 +
   `run_id`. See Decisions log + Tier 1. **All open questions now resolved.**
