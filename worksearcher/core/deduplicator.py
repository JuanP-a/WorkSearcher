from worksearcher.core.models import Job


def deduplicate(jobs: list[Job], seen: set[str]) -> list[Job]:
    return [j for j in jobs if j.fingerprint not in seen]
