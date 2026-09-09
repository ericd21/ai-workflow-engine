"""FastAPI backend, driven by TestClient. No network: mock LLM provider + call_llm stubs."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.llm import extractor as extractor_mod
from tests.helpers import raw_llm_response


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _payload(**overrides):
    body = {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "phone": None,
        "department": "billing",
        "message": "My invoice is wrong and I need a refund for the duplicate charge.",
    }
    body.update(overrides)
    return body


def test_index_serves_contact_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="contactForm"' in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_static_assets_served(client):
    assert client.get("/static/css/contact.css").status_code == 200
    assert client.get("/static/js/contact.js").status_code == 200


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_submit_success_via_mock_provider(client):
    # LLM_PROVIDER=mock (conftest) → real mock provider classifies this as billing.
    r = client.post("/submit", json=_payload(department="billing"))
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert body["target"] == "billing_queue"
    assert body["final_department"] == "billing"
    assert body["human_review_required"] is False


def test_submit_success_shape_matches_contact_js(client, monkeypatch):
    monkeypatch.setattr(extractor_mod, "call_llm", lambda _p: raw_llm_response(department="support"))
    r = client.post("/submit", json=_payload(department="support",
                                             message="The application keeps crashing on startup."))
    body = r.json()
    assert set(body) == {
        "run_id", "target", "sla", "final_department",
        "priority", "human_review_required", "summary",
    }


def test_submit_short_message_returns_flat_422(client):
    r = client.post("/submit", json=_payload(message="too short"))
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert "message" in r.json()["detail"]


def test_submit_missing_department_returns_422(client):
    body = _payload()
    del body["department"]
    r = client.post("/submit", json=body)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_submit_neither_email_nor_phone_returns_422(client):
    r = client.post("/submit", json=_payload(email=None, phone=None))
    assert r.status_code == 422
    assert "email or phone" in r.json()["detail"].lower()


def test_submit_engine_failure_returns_502_with_run_id(client, monkeypatch):
    def boom(_prompt):
        raise RuntimeError("llm is down")

    monkeypatch.setattr(extractor_mod, "call_llm", boom)
    r = client.post("/submit", json=_payload(department="other"))
    assert r.status_code == 502
    body = r.json()
    assert body["detail"]
    assert body["run_id"]


def test_submit_unexpected_exception_returns_502(client, monkeypatch):
    from app.api import main as api_main

    def kaboom(_intake):
        raise ValueError("something totally unexpected")

    monkeypatch.setattr(api_main.engine, "run_workflow", kaboom)
    r = client.post("/submit", json=_payload(department="other"))
    assert r.status_code == 502
    assert "internal error" in r.json()["detail"]


def test_submit_department_override_reflected_in_response(client):
    # User picks "sales" but the message is clearly billing → mock overrides at 0.82.
    r = client.post("/submit", json=_payload(department="sales"))
    assert r.status_code == 200
    assert r.json()["final_department"] == "billing"
