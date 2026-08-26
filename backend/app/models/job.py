from pydantic import BaseModel, Field, StringConstraints
from typing import Optional, Annotated
from datetime import datetime, timezone

class JobRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(..., description="The research query")

class JobResponse(BaseModel):
    job_id: str
    status: str
    report: Optional[str] = None

class Job(BaseModel):
    job_id: str
    query: str
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED
    report: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
