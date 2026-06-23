"""Shared test fixtures and helpers."""
import pytest


class FakeSettings:
    """Implements the full Settings interface so tests don't diverge when new fields are added."""
    META_PHONE_NUMBER_ID = "123456789"
    META_ACCESS_TOKEN = "fake_token"
    META_RECIPIENT_PHONE = "521234567890"
    META_API_VERSION = "v21.0"
    keywords_list = ["python", "backend", "cybersecurity"]
    MAX_YEARS_EXPERIENCE = 3
    MAX_JOB_AGE_DAYS = 30
    blacklist_list: list = []
    filter_languages_list: list = ["en", "es"]
    MIN_SALARY_USD_MONTHLY = None


@pytest.fixture
def fake_settings() -> FakeSettings:
    return FakeSettings()
