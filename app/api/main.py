"""FastAPI backend: serves the contact form and runs submissions through the engine.

    contact.html form
      → contact.js  (client-side validation, JSON body)
      → POST /submit  (FastAPI validates it as IntakeRequest → 422 on bad input)
      → run_in_threadpool(engine.run_workflow, intake)   (graph runs off the loop)
      → 200 SubmitResponse {run_id, target, sla, ...}   or   502 {detail, run_id}
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.logging_config import configure_logging, get_logger
from app.schemas.intake import Department, IntakeRequest
from app.schemas.routing import SLA, RoutingTarget
from app.schemas.triage import Priority
from app.workflow.engine import engine
from app.workflow.errors import WorkflowError

_APP_DIR = Path(__file__).resolve().parent.parent  # .../app
_STATIC_DIR = _APP_DIR / "static"
_CONTACT_PAGE = _APP_DIR / "templates" / "contact.html"

logger = get_logger(__name__)


class SubmitResponse(BaseModel):
    run_id: str
    target: RoutingTarget
    sla: SLA
    final_department: Department
    priority: Priority
    human_review_required: bool
    summary: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    logger.info("API starting", extra={"event": "api_startup"})
    yield


app = FastAPI(title="AI Workflow Engine", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def _flatten_validation_error(_request, exc: RequestValidationError) -> JSONResponse:
    """Return a single readable string in `detail` so contact.js can display it."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts) or "invalid request"})


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_CONTACT_PAGE)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/submit", response_model=SubmitResponse)
async def submit(intake: IntakeRequest):
    try:
        result = await run_in_threadpool(engine.run_workflow, intake)
    except WorkflowError as exc:
        logger.warning(
            "Submission failed in the workflow",
            extra={"run_id": exc.run_id, "event": "submit_failure", "errors": exc.errors},
        )
        return JSONResponse(
            status_code=502,
            content={
                "detail": "; ".join(exc.errors) or "workflow failed",
                "run_id": exc.run_id,
            },
        )
    except Exception as exc:  # unexpected — don't leak internals to the client
        logger.exception("Submission crashed", extra={"event": "submit_error"})
        return JSONResponse(status_code=502, content={"detail": f"internal error: {exc}"})

    routing = result["routing"]
    return SubmitResponse(
        run_id=result["run_id"],
        target=routing.target,
        sla=routing.sla,
        final_department=routing.final_department,
        priority=routing.priority,
        human_review_required=routing.human_review_required,
        summary=routing.summary,
    )
