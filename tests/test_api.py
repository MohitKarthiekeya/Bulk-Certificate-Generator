"""Core API tests. Set DATABASE_URL and CERTIFICATE_STORAGE to isolated temp paths when running."""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_certificates.db"
os.environ["CERTIFICATE_STORAGE"] = "./test_storage"

from app.database import Base, engine  # noqa: E402
from app import main as main_module  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def sample_payload():
    return {"event_name": "Spring Workshop", "course_name": "First Aid", "issuer": "Northside Center",
            "recipients": [{"name": "Avery Shah", "email": "avery@example.com", "completion_date": "2026-05-12"}]}


def get_finished_job(payload):
    created = client.post("/api/v1/jobs", json=payload).json()
    return client.get("/api/v1/jobs/" + created["job_id"]).json()


def test_create_job_and_generation_status():
    response = client.post("/api/v1/jobs", json=sample_payload())
    assert response.status_code == 202
    job = response.json()
    assert job["total"] == 1
    status = client.get("/api/v1/jobs/" + job["job_id"]).json()
    assert status["completed"] == 1
    assert status["recipients"][0]["status"] == "completed"


def test_invalid_recipient_is_reported_without_blocking_valid_one():
    payload = sample_payload()
    payload["recipients"].append({"name": "", "email": "not-an-email"})
    result = get_finished_job(payload)
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["recipients"][1]["error"]


def test_certificate_failure_does_not_stop_other_recipients(monkeypatch):
    original_generator = main_module.create_certificate

    def fail_for_jordan(*args, **kwargs):
        if kwargs.get("name") == "Jordan Lee":
            raise RuntimeError("simulated rendering problem")
        return original_generator(*args, **kwargs)

    monkeypatch.setattr(main_module, "create_certificate", fail_for_jordan)
    payload = sample_payload()
    payload["recipients"].append({"name": "Jordan Lee", "email": "jordan@example.com"})
    result = get_finished_job(payload)

    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["recipients"][1]["status"] == "failed"


def test_certificate_can_be_downloaded_individually_and_as_zip():
    job = client.post("/api/v1/jobs", json=sample_payload()).json()
    status = client.get("/api/v1/jobs/" + job["job_id"]).json()
    recipient_id = status["recipients"][0]["id"]
    individual = client.get("/api/v1/jobs/" + job["job_id"] + "/certificates/" + str(recipient_id))
    bundle = client.get("/api/v1/jobs/" + job["job_id"] + "/certificates")
    assert individual.status_code == 200 and individual.content.startswith(b"%PDF")
    assert bundle.status_code == 200 and bundle.headers["content-type"] == "application/zip"


def test_unknown_job_returns_404():
    assert client.get("/api/v1/jobs/missing").status_code == 404
