# Bulk Certificate Generator

This FastAPI service creates completion certificates for a group of participants from one request. It stores job progress in SQLite and creates one PDF per valid recipient using a fixed certificate design.

## Set up

Use Python 3.10 or newer. From the project folder, create a virtual environment and install the dependencies:

~~~bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
~~~

## Run the API

~~~bash
uvicorn app.main:app --reload
~~~

The API runs at http://127.0.0.1:8000. Interactive documentation is at /docs. By default, job data is saved in certificates.db and generated PDFs go under storage/. Set DATABASE_URL or CERTIFICATE_STORAGE to use different locations.

## Submit a bulk request

Send POST /api/v1/jobs with the event, course, issuer, and recipient list. Each recipient needs a name and valid email address; completion_date is optional.

~~~json
{
  "event_name": "Spring Workshop",
  "course_name": "First Aid Basics",
  "issuer": "Northside Learning Center",
  "recipients": [
    {"name": "Avery Shah", "email": "avery@example.com", "completion_date": "2026-05-12"},
    {"name": "Jordan Lee", "email": "jordan@example.com"}
  ]
}
~~~

The response includes a job_id and an outcome for every recipient. Invalid entries are marked as failed while valid recipients continue through generation.

## Check progress and download certificates

- GET /api/v1/jobs/{job_id} returns job status, counts, and each recipient's result.
- GET /api/v1/jobs/{job_id}/certificates/{recipient_id} downloads one PDF.
- GET /api/v1/jobs/{job_id}/certificates downloads all completed PDFs as a ZIP.

A certificate returns 409 while it is still being generated. Unknown jobs or recipients return 404.

## Run the tests

~~~bash
pytest
~~~

The tests cover job creation, recipient validation, progress results, an individual generation failure, and PDF and ZIP downloads.

## Design notes

The endpoint saves the job first, returns 202 Accepted, and generates certificates in a FastAPI background task. Results are saved recipient by recipient, so one bad entry does not block the rest. This keeps the project easy to run locally; because the worker lives in the API process, a restart can interrupt an active job. A durable queue would be a sensible next step for production or multi-instance deployments.
