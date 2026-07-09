from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, computed_field, field_validator


class JobSource(StrEnum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"
    WWR = "weworkremotely"
    CYBERSECJOBS = "cybersecjobs"
    COMPUTRABAJO = "computrabajo"
    BUMERAN = "bumeran"
    HIMALAYAS = "himalayas"
    HACKERNEWS = "hackernews"
    OCC = "occ"
    GETONBOARD = "getonboard"


class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str
    source: JobSource
    is_remote: bool
    description: str = ""
    posted_at: datetime | None = None
    min_salary_usd_monthly: float | None = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError(f"url scheme must be http/https, got: {v!r}")
        return v

    @computed_field
    @property
    def fingerprint(self) -> str:
        raw = f"{self.title}{self.company}{self.url}".lower()
        return sha256(raw.encode()).hexdigest()


class Company(BaseModel):
    """A cold-outreach lead discovered near a configured coordinate — not a Job.

    No posted_at/age field: unlike a job posting, a local business lead
    doesn't expire after MAX_JOB_AGE_DAYS.
    """

    name: str
    website: str
    latitude: float
    longitude: float
    email: str | None = None
    email_is_hr_context: bool = False
    status: Literal["pending", "no_email_found"] = "pending"

    @computed_field
    @property
    def fingerprint(self) -> str:
        raw = f"{self.name}{self.website}".lower()
        return sha256(raw.encode()).hexdigest()
