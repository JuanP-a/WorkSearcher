from worksearcher.core.models import Company, Job, JobSource


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


def test_job_source_enum_covers_all_platforms():
    # All 12 target platforms must be represented
    assert JobSource.LINKEDIN == "linkedin"
    assert JobSource.INDEED == "indeed"
    assert JobSource.GLASSDOOR == "glassdoor"
    assert JobSource.REMOTEOK == "remoteok"
    assert JobSource.REMOTIVE == "remotive"
    assert JobSource.WWR == "weworkremotely"
    assert JobSource.CYBERSECJOBS == "cybersecjobs"
    assert JobSource.COMPUTRABAJO == "computrabajo"
    assert JobSource.BUMERAN == "bumeran"
    assert JobSource.HIMALAYAS == "himalayas"
    assert JobSource.HACKERNEWS == "hackernews"
    assert JobSource.OCC == "occ"


def test_fingerprint_differs_by_company():
    # Different companies on the same URL must yield different fingerprints
    # (ensures company is part of the hash input)
    base = dict(
        title="Dev",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    job1 = Job(**base, company="CompanyA")
    job2 = Job(**base, company="CompanyB")
    assert job1.fingerprint != job2.fingerprint


def test_keywords_soc_matches_substring():
    # "soc" intentionally matches substrings (e.g. "SOC Analyst")
    # Documented here so the behaviour is explicit and reviewed if changed
    from worksearcher.core.filters import is_relevant

    job = Job(
        title="SOC Analyst",
        company="Co",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    assert is_relevant(job, ["soc"]) is True
    # Substring match: "social" also contains "soc" — accepted tradeoff for simplicity
    social_job = Job(
        title="Social Media Manager",
        company="Co",
        location="Remote",
        url="https://example.com/2",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    assert is_relevant(social_job, ["soc"]) is True  # known behaviour, not a bug


def test_job_has_min_salary_field():
    job = Job(
        title="Dev",
        company="Co",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
    )
    assert job.min_salary_usd_monthly is None


def test_job_accepts_salary_value():
    job = Job(
        title="Dev",
        company="Co",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.REMOTEOK,
        is_remote=True,
        min_salary_usd_monthly=1500.0,
    )
    assert job.min_salary_usd_monthly == 1500.0


def test_job_source_occ_value():
    from worksearcher.core.models import JobSource

    assert JobSource.OCC == "occ"


def test_company_fingerprint_same_name_and_website_is_stable():
    kwargs = dict(name="Acme Corp", website="https://acme.mx", latitude=20.1, longitude=-100.8)
    assert Company(**kwargs).fingerprint == Company(**kwargs).fingerprint


def test_company_fingerprint_differs_by_website():
    base = dict(name="Acme Corp", latitude=20.1, longitude=-100.8)
    company1 = Company(**base, website="https://acme.mx")
    company2 = Company(**base, website="https://acme.com")
    assert company1.fingerprint != company2.fingerprint


def test_company_fingerprint_differs_by_name():
    base = dict(website="https://acme.mx", latitude=20.1, longitude=-100.8)
    company1 = Company(**base, name="Acme Corp")
    company2 = Company(**base, name="Acme Industries")
    assert company1.fingerprint != company2.fingerprint


def test_company_defaults_to_pending_with_no_email():
    company = Company(name="Acme Corp", website="https://acme.mx", latitude=20.1, longitude=-100.8)
    assert company.status == "pending"
    assert company.email is None
    assert company.email_is_hr_context is False
