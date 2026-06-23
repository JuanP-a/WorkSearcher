from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, computed_field


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


class Job(BaseModel):
    title: str
    company: str
    location: str
    url: str
    source: JobSource
    is_remote: bool
    description: str = ""
    posted_at: datetime | None = None

    @computed_field
    @property
    def fingerprint(self) -> str:
        raw = f"{self.title}{self.company}{self.url}".lower()
        return sha256(raw.encode()).hexdigest()
