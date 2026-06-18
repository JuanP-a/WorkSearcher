from enum import StrEnum
from hashlib import sha256
from datetime import datetime

from pydantic import BaseModel, model_validator


class JobSource(StrEnum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"


class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str
    source: JobSource
    is_remote: bool
    description: str = ""
    posted_at: datetime | None = None
    fingerprint: str = ""

    @model_validator(mode="after")
    def compute_fingerprint(self) -> "Job":
        raw = f"{self.title}{self.company}{self.url}".lower()
        self.fingerprint = sha256(raw.encode()).hexdigest()
        return self
