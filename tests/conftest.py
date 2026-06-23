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


@pytest.fixture
def fake_settings() -> FakeSettings:
    return FakeSettings()
