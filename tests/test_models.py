from worksearcher.core.models import Job, JobSource


def test_job_fingerprint_is_computed_on_creation():
    job = Job(
        title="Python Developer",
        company="Acme Corp",
        location="Remote",
        url="https://example.com/job/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    assert job.fingerprint != ""
    assert len(job.fingerprint) == 64  # SHA256 hex digest


def test_same_data_produces_same_fingerprint():
    kwargs = dict(
        title="Python Developer",
        company="Acme Corp",
        location="Remote",
        url="https://example.com/job/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    job1 = Job(**kwargs)
    job2 = Job(**kwargs)
    assert job1.fingerprint == job2.fingerprint


def test_different_url_produces_different_fingerprint():
    base = dict(
        title="Dev",
        company="Co",
        location="Remote",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    job1 = Job(**base, url="https://example.com/1")
    job2 = Job(**base, url="https://example.com/2")
    assert job1.fingerprint != job2.fingerprint


def test_fingerprint_is_case_insensitive():
    base = dict(company="Co", location="Remote", source=JobSource.REMOTEOK, is_remote=True)
    job1 = Job(**base, title="Python Developer", url="https://example.com/1")
    job2 = Job(**base, title="PYTHON DEVELOPER", url="https://example.com/1")
    assert job1.fingerprint == job2.fingerprint


def test_job_source_enum_values():
    assert JobSource.LINKEDIN == "linkedin"
    assert JobSource.INDEED == "indeed"
    assert JobSource.GLASSDOOR == "glassdoor"
    assert JobSource.REMOTEOK == "remoteok"
    assert JobSource.REMOTIVE == "remotive"
