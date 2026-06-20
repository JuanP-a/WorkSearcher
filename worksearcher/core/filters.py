from worksearcher.core.models import Job


def is_relevant(job: Job, keywords: list[str]) -> bool:
    if not job.is_remote:
        return False
    searchable = f"{job.title} {job.description}".lower()
    return any(kw.lower() in searchable for kw in keywords)


def filter_jobs(jobs: list[Job], keywords: list[str]) -> list[Job]:
    return [j for j in jobs if is_relevant(j, keywords)]
