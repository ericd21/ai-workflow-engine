# Multi-stage build: install deps in a venv, then copy only the venv + app
# code into a slim, non-root runtime image.

FROM python:3.13-slim AS builder

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN pip install "poetry>=2.0,<3.0"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY app ./app


FROM python:3.13-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
