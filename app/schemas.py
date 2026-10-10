from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateJobRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=200)
    course_name: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=200)
    recipients: list[dict[str, Any]] = Field(min_length=1, max_length=5000)


class RecipientResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    status: str
    error: str | None = None
    download_url: str | None = None


class JobResult(BaseModel):
    job_id: str
    status: str
    total: int
    completed: int
    failed: int
    pending: int
    recipients: list[RecipientResult]
