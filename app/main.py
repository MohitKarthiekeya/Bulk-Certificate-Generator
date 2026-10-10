import io
import re
import uuid
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.certificates import create_certificate
from app.database import Base, SessionLocal, engine, ensure_storage, get_db
from app.models import GenerationJob, JobRecipient
from app.schemas import CreateJobRequest


Base.metadata.create_all(bind=engine)
app = FastAPI(title="Bulk Certificate Generator", version="1.0.0",
              description="Create and retrieve completion certificates in bulk.")


def validate_recipient(raw: dict) -> tuple[str, str, str, str | None]:
    name = str(raw.get("name") or "").strip()
    email = str(raw.get("email") or "").strip().lower()
    completion_date = str(raw.get("completion_date") or "").strip()
    if not name or len(name) > 200:
        return name, email, completion_date, "Name is required and must be 200 characters or fewer."
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return name, email, completion_date, "A valid email address is required."
    if completion_date and len(completion_date) > 40:
        return name, email, completion_date, "Completion date must be 40 characters or fewer."
    return name, email, completion_date, None


def render_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()
        storage = ensure_storage()
        for recipient in db.query(JobRecipient).filter_by(job_id=job_id).all():
            if recipient.status == "failed":
                continue
            try:
                filename = f"{recipient.id}.pdf"
                destination = storage / job_id / filename
                create_certificate(destination, name=recipient.name, course_name=job.course_name,
                                   event_name=job.event_name, issuer=job.issuer,
                                   completion_date=recipient.completion_date or "Not specified")
                recipient.file_path = str(destination)
                recipient.status = "completed"
                recipient.error = None
            except Exception as exc:  # Keep a single bad certificate from stopping the rest.
                recipient.status = "failed"
                recipient.error = f"Certificate could not be generated: {type(exc).__name__}"
            db.commit()
        recipients = db.query(JobRecipient).filter_by(job_id=job_id).all()
        job.status = "completed" if all(r.status != "pending" for r in recipients) else "failed"
        db.commit()
    finally:
        db.close()


def serialize_job(db: Session, job: GenerationJob) -> dict:
    recipients = db.query(JobRecipient).filter_by(job_id=job.id).order_by(JobRecipient.id).all()
    completed = sum(r.status == "completed" for r in recipients)
    failed = sum(r.status == "failed" for r in recipients)
    return {
        "job_id": job.id,
        "status": job.status,
        "total": len(recipients),
        "completed": completed,
        "failed": failed,
        "pending": len(recipients) - completed - failed,
        "recipients": [{"id": r.id, "name": r.name, "email": r.email, "status": r.status,
                        "error": r.error,
                        "download_url": f"/api/v1/jobs/{job.id}/certificates/{r.id}" if r.status == "completed" else None}
                       for r in recipients],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/jobs", status_code=202)
def create_job(payload: CreateJobRequest, background_tasks: BackgroundTasks,
               db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    job = GenerationJob(id=job_id, event_name=payload.event_name.strip(),
                        course_name=payload.course_name.strip(), issuer=payload.issuer.strip(),
                        status="queued")
    db.add(job)
    seen_emails: set[str] = set()
    for raw in payload.recipients:
        name, email, completion_date, error = validate_recipient(raw)
        if not error and email in seen_emails:
            error = "This email address appears more than once in the request."
        if email:
            seen_emails.add(email)
        db.add(JobRecipient(job_id=job_id, name=name, email=email,
                            completion_date=completion_date,
                            status="failed" if error else "pending", error=error))
    db.commit()
    background_tasks.add_task(render_job, job_id)
    return serialize_job(db, db.get(GenerationJob, job_id))


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    return serialize_job(db, job)


@app.get("/api/v1/jobs/{job_id}/certificates/{recipient_id}")
def get_certificate(job_id: str, recipient_id: int, db: Session = Depends(get_db)):
    recipient = db.query(JobRecipient).filter_by(job_id=job_id, id=recipient_id).first()
    if recipient is None:
        raise HTTPException(status_code=404, detail="Certificate recipient not found.")
    if recipient.status != "completed" or not recipient.file_path:
        raise HTTPException(status_code=409, detail="This certificate is not ready for download.")
    path = Path(recipient.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Generated certificate file is missing.")
    return FileResponse(path, media_type="application/pdf", filename=f"certificate-{recipient.id}.pdf")


@app.get("/api/v1/jobs/{job_id}/certificates")
def get_certificates_zip(job_id: str, db: Session = Depends(get_db)):
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    recipients = db.query(JobRecipient).filter_by(job_id=job_id, status="completed").all()
    if not recipients:
        raise HTTPException(status_code=409, detail="No certificates are ready for download.")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for recipient in recipients:
            path = Path(recipient.file_path or "")
            if path.is_file():
                safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", recipient.name).strip("_") or "recipient"
                bundle.write(path, f"{safe_name}-{recipient.id}.pdf")
    archive.seek(0)
    return StreamingResponse(archive, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="certificates-{job_id}.zip"'})
