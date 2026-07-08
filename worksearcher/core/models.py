from datetime import datetime
from enum import StrEnum
from hashlib import sha256

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
