import httpx
import pytest
import respx

from worksearcher.core.models import Company, Job, JobSource
from worksearcher.notifier.whatsapp import (
    _build_message,
    _build_outreach_message,
    send_digest,
    send_outreach_digest,
)

_MAX_JOBS_PER_MESSAGE = 10  # matches Settings.MAX_JOBS_PER_MESSAGE default
_MAX_COMPANIES_PER_MESSAGE = 30  # matches Settings.OUTREACH_MAX_COMPANIES_PER_MESSAGE default


def _job(n: int, source: JobSource = JobSource.REMOTEOK) -> Job:
    return Job(
        title=f"Job {n}",
        company=f"Company {n}",
        location="Remote",
        url=f"https://example.com/job/{n}",
        source=source,
        is_remote=True,
    )


def _company(n: int) -> Company:
    return Company(
        name=f"Company {n}",
        website=f"https://company{n}.mx",
        latitude=20.1,
        longitude=-100.8,
        email=f"rh{n}@company{n}.mx",
    )


# --- _build_message ---


def test_build_message_header():
    msg = _build_message([_job(1)], _MAX_JOBS_PER_MESSAGE)
    assert "*WorkSearcher — nuevas ofertas:*" in msg


def test_build_message_includes_title_and_company():
    msg = _build_message([_job(1)], _MAX_JOBS_PER_MESSAGE)
    assert "Job 1" in msg
    assert "Company 1" in msg


def test_build_message_includes_url():
    msg = _build_message([_job(1)], _MAX_JOBS_PER_MESSAGE)
    assert "https://example.com/job/1" in msg


def test_build_message_exact_limit_no_overflow_line():
    jobs = [_job(i) for i in range(_MAX_JOBS_PER_MESSAGE)]
    msg = _build_message(jobs, _MAX_JOBS_PER_MESSAGE)
    assert "más guardadas" not in msg


def test_build_message_overflow_shows_count():
    jobs = [_job(i) for i in range(_MAX_JOBS_PER_MESSAGE + 5)]
    msg = _build_message(jobs, _MAX_JOBS_PER_MESSAGE)
    assert "5 más guardadas en DB" in msg


def test_build_message_truncates_at_max():
    jobs = [_job(i) for i in range(20)]
    msg = _build_message(jobs, _MAX_JOBS_PER_MESSAGE)
    assert f"Job {_MAX_JOBS_PER_MESSAGE - 1}" in msg
    assert f"Job {_MAX_JOBS_PER_MESSAGE}" not in msg


def test_build_message_single_job():
    msg = _build_message([_job(1)], _MAX_JOBS_PER_MESSAGE)
    assert msg.count("•") == 1


def test_build_message_empty_list():
    msg = _build_message([], _MAX_JOBS_PER_MESSAGE)
    assert "*WorkSearcher — nuevas ofertas:*" in msg
    assert "•" not in msg


# --- send_digest ---


@pytest.mark.asyncio
@respx.mock
async def test_send_digest_sends_correct_payload(fake_settings):
    route = respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})
    )
    await send_digest([_job(1)], fake_settings)

    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer fake_token"
    assert request.headers["Content-Type"] == "application/json"
    body = request.content
    import json

    payload = json.loads(body)
    assert payload["to"] == "521234567890"
    assert payload["messaging_product"] == "whatsapp"
    assert payload["type"] == "text"
    assert "Job 1" in payload["text"]["body"]


@pytest.mark.asyncio
@respx.mock
async def test_send_digest_returns_true_on_success(fake_settings):
    respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})
    )
    result = await send_digest([_job(1)], fake_settings)
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_send_digest_returns_false_on_401(fake_settings):
    respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        return_value=httpx.Response(401, json={"error": {"code": 190, "message": "Invalid token"}})
    )
    result = await send_digest([_job(1)], fake_settings)
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_send_digest_returns_false_on_network_error(fake_settings):
    respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        side_effect=httpx.ConnectError("Network unreachable")
    )
    result = await send_digest([_job(1)], fake_settings)
    assert result is False


@pytest.mark.asyncio
async def test_send_digest_returns_false_for_empty_list(fake_settings):
    result = await send_digest([], fake_settings)
    assert result is False


# --- _build_outreach_message ---


def test_build_outreach_message_header_distinct_from_jobs():
    msg = _build_outreach_message([_company(1)], _MAX_COMPANIES_PER_MESSAGE)
    assert "*WorkSearcher — nuevas ofertas:*" not in msg
    assert "empresas" in msg.lower()


def test_build_outreach_message_includes_name_email_website():
    msg = _build_outreach_message([_company(1)], _MAX_COMPANIES_PER_MESSAGE)
    assert "Company 1" in msg
    assert "rh1@company1.mx" in msg
    assert "https://company1.mx" in msg


def test_build_outreach_message_overflow_shows_count():
    companies = [_company(i) for i in range(_MAX_COMPANIES_PER_MESSAGE + 5)]
    msg = _build_outreach_message(companies, _MAX_COMPANIES_PER_MESSAGE)
    assert "5 más guardadas en DB" in msg


def test_build_outreach_message_empty_list():
    msg = _build_outreach_message([], _MAX_COMPANIES_PER_MESSAGE)
    assert "•" not in msg


# --- send_outreach_digest ---


@pytest.mark.asyncio
@respx.mock
async def test_send_outreach_digest_sends_correct_payload(fake_settings):
    route = respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})
    )
    await send_outreach_digest([_company(1)], fake_settings)

    assert route.called
    import json

    payload = json.loads(route.calls[0].request.content)
    assert "Company 1" in payload["text"]["body"]
    assert "rh1@company1.mx" in payload["text"]["body"]


@pytest.mark.asyncio
@respx.mock
async def test_send_outreach_digest_returns_true_on_success(fake_settings):
    respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})
    )
    result = await send_outreach_digest([_company(1)], fake_settings)
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_send_outreach_digest_returns_false_on_401(fake_settings):
    respx.post("https://graph.facebook.com/v21.0/123456789/messages").mock(
        return_value=httpx.Response(401, json={"error": {"code": 190, "message": "Invalid token"}})
    )
    result = await send_outreach_digest([_company(1)], fake_settings)
    assert result is False


@pytest.mark.asyncio
async def test_send_outreach_digest_returns_false_for_empty_list(fake_settings):
    result = await send_outreach_digest([], fake_settings)
    assert result is False
