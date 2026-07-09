import logging
import sqlite3

import httpx
import pytest
import respx

from worksearcher.core.models import Company
from worksearcher.outreach.discovery import discover_companies
from worksearcher.outreach.email_extractor import extract_email
from worksearcher.outreach.pipeline import run_outreach_pipeline
from worksearcher.storage.database import init_db


def _overpass_response(elements: list[dict]) -> dict:
    return {"version": 0.6, "elements": elements}


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_parses_node_element(fake_settings):
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(
            200,
            json=_overpass_response(
                [
                    {
                        "type": "node",
                        "lat": 20.5,
                        "lon": -100.9,
                        "tags": {"name": "Acme Corp", "website": "https://acme.mx"},
                    }
                ]
            ),
        )
    )
    companies = await discover_companies(fake_settings)
    assert len(companies) == 1
    assert companies[0].name == "Acme Corp"
    assert companies[0].website == "https://acme.mx"
    assert companies[0].latitude == 20.5
    assert companies[0].longitude == -100.9


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_parses_way_center(fake_settings):
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(
            200,
            json=_overpass_response(
                [
                    {
                        "type": "way",
                        "center": {"lat": 21.0, "lon": -101.0},
                        "tags": {"name": "Beta Inc", "website": "https://beta.mx"},
                    }
                ]
            ),
        )
    )
    companies = await discover_companies(fake_settings)
    assert len(companies) == 1
    assert companies[0].latitude == 21.0
    assert companies[0].longitude == -101.0


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_skips_element_without_website(fake_settings):
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(
            200,
            json=_overpass_response(
                [{"type": "node", "lat": 1, "lon": 1, "tags": {"name": "No Website Co"}}]
            ),
        )
    )
    companies = await discover_companies(fake_settings)
    assert companies == []


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_skips_element_without_name(fake_settings):
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(
            200,
            json=_overpass_response(
                [{"type": "node", "lat": 1, "lon": 1, "tags": {"website": "https://x.mx"}}]
            ),
        )
    )
    companies = await discover_companies(fake_settings)
    assert companies == []


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_returns_empty_on_http_error(fake_settings):
    respx.post("https://overpass-api.de/api/interpreter").mock(return_value=httpx.Response(500))
    companies = await discover_companies(fake_settings)
    assert companies == []


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_logs_exception_type_on_timeout(fake_settings, caplog):
    # httpx.ReadTimeout has an empty str() — logging only "%s" of the
    # exception produces an unhelpful "failed: " with nothing after the
    # colon. The exception type must be visible in the log too.
    respx.post("https://overpass-api.de/api/interpreter").mock(side_effect=httpx.ReadTimeout(""))
    with caplog.at_level(logging.ERROR, logger="worksearcher.outreach.discovery"):
        await discover_companies(fake_settings)

    assert any("ReadTimeout" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_discover_companies_raises_without_coordinates(fake_settings):
    fake_settings.OUTREACH_LAT = None
    with pytest.raises(ValueError):
        await discover_companies(fake_settings)


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_uses_configured_overpass_url(fake_settings):
    # overpass-api.de intermittently 406s on the whole community (see
    # docs/contexto/errores-conocidos.md) — the endpoint must be a config
    # value, not a hardcoded constant, so a mirror swap needs no code change.
    fake_settings.OUTREACH_OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
    route = respx.post("https://overpass.kumi.systems/api/interpreter").mock(
        return_value=httpx.Response(200, json=_overpass_response([]))
    )
    await discover_companies(fake_settings)
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_discover_companies_respects_max_companies_cap(fake_settings):
    fake_settings.OUTREACH_MAX_COMPANIES_PER_RUN = 1
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(
            200,
            json=_overpass_response(
                [
                    {
                        "type": "node",
                        "lat": 1,
                        "lon": 1,
                        "tags": {"name": "A", "website": "https://a.mx"},
                    },
                    {
                        "type": "node",
                        "lat": 2,
                        "lon": 2,
                        "tags": {"name": "B", "website": "https://b.mx"},
                    },
                ]
            ),
        )
    )
    companies = await discover_companies(fake_settings)
    assert len(companies) == 1


def _company(website: str = "https://acme.mx") -> Company:
    return Company(name="Acme Corp", website=website, latitude=20.1, longitude=-100.8)


def _no_robots(base: str):
    respx.get(f"{base}/robots.txt").mock(return_value=httpx.Response(404))


@pytest.mark.asyncio
@respx.mock
async def test_extract_email_prefers_hr_context_over_fallback(fake_settings):
    fake_settings.outreach_contact_paths_list = ["/contacto"]
    _no_robots("https://acme.mx")
    respx.get("https://acme.mx").mock(
        return_value=httpx.Response(
            200,
            html=(
                "<a href='mailto:ventas@acme.mx'>Ventas</a>"
                "<p>Recursos Humanos: <a href='mailto:rh@acme.mx'>rh@acme.mx</a></p>"
            ),
        )
    )
    result = await extract_email(_company(), fake_settings)
    assert result.email == "rh@acme.mx"
    assert result.email_is_hr_context is True
    assert result.status == "pending"


@pytest.mark.asyncio
@respx.mock
async def test_extract_email_falls_back_to_first_email_without_hr_context(fake_settings):
    fake_settings.outreach_contact_paths_list = ["/contacto"]
    _no_robots("https://acme.mx")
    respx.get("https://acme.mx/").mock(
        return_value=httpx.Response(200, html="<a href='mailto:info@acme.mx'>Info</a>")
    )
    respx.get("https://acme.mx/contacto").mock(
        return_value=httpx.Response(200, html="<p>Sin correo</p>")
    )
    result = await extract_email(_company(), fake_settings)
    assert result.email == "info@acme.mx"
    assert result.email_is_hr_context is False
    assert result.status == "pending"


@pytest.mark.asyncio
@respx.mock
async def test_extract_email_no_email_found_sets_status(fake_settings):
    fake_settings.outreach_contact_paths_list = ["/contacto"]
    _no_robots("https://acme.mx")
    respx.get("https://acme.mx/").mock(return_value=httpx.Response(200, html="<p>Nada aqui</p>"))
    respx.get("https://acme.mx/contacto").mock(
        return_value=httpx.Response(200, html="<p>Nada aqui tampoco</p>")
    )
    result = await extract_email(_company(), fake_settings)
    assert result.email is None
    assert result.status == "no_email_found"


@pytest.mark.asyncio
@respx.mock
async def test_extract_email_respects_robots_disallow(fake_settings):
    fake_settings.outreach_contact_paths_list = ["/contacto"]
    respx.get("https://acme.mx/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /contacto\n")
    )
    respx.get("https://acme.mx/").mock(return_value=httpx.Response(200, html="<p>Sin correo</p>"))
    # /contacto DOES have a findable email — mocked (not left unmocked) so a
    # broken robots check can't hide behind a swallowed request error and
    # coincidentally still pass. If the disallow is ignored, this email
    # would be picked up and the assertions below would fail.
    respx.get("https://acme.mx/contacto").mock(
        return_value=httpx.Response(200, html="<a href='mailto:rh@acme.mx'>Recursos Humanos</a>")
    )
    result = await extract_email(_company(), fake_settings)
    assert result.email is None
    assert result.status == "no_email_found"


@pytest.mark.asyncio
@respx.mock
async def test_extract_email_skips_failed_path_and_continues(fake_settings):
    fake_settings.outreach_contact_paths_list = ["/contacto"]
    _no_robots("https://acme.mx")
    respx.get("https://acme.mx/").mock(return_value=httpx.Response(500))
    respx.get("https://acme.mx/contacto").mock(
        return_value=httpx.Response(200, html="<a href='mailto:rh@acme.mx'>Recursos Humanos</a>")
    )
    result = await extract_email(_company(), fake_settings)
    assert result.email == "rh@acme.mx"
    assert result.email_is_hr_context is True


# --- run_outreach_pipeline ---


def _lead(n: int, email: str | None = "rh@acme.mx") -> Company:
    return Company(
        name=f"Company {n}",
        website=f"https://company{n}.mx",
        latitude=20.1,
        longitude=-100.8,
        email=email,
        status="pending" if email else "no_email_found",
    )


def _make_fake_discover(companies: list[Company]):
    async def discover(config) -> list[Company]:
        return companies

    return discover


def _make_fake_extract(overrides: dict | None = None):
    """Identity extractor by default; `overrides` maps company name -> Company to return."""

    async def extract(company: Company, config) -> Company:
        if overrides and company.name in overrides:
            return overrides[company.name]
        return company

    return extract


@pytest.mark.asyncio
async def test_outreach_pipeline_saves_and_notifies_new_companies(
    tmp_path, monkeypatch, fake_settings
):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    companies = [_lead(1), _lead(2)]
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.discover_companies", _make_fake_discover(companies)
    )
    monkeypatch.setattr("worksearcher.outreach.pipeline.extract_email", _make_fake_extract())
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.get_connection", lambda path: sqlite3.connect(db_path)
    )

    notified = []

    async def fake_send_outreach_digest(companies, config):
        notified.extend(companies)
        return True

    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.send_outreach_digest", fake_send_outreach_digest
    )

    await run_outreach_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()

    assert count == 2
    assert len(notified) == 2


@pytest.mark.asyncio
async def test_outreach_pipeline_saves_but_does_not_notify_no_email_found(
    tmp_path, monkeypatch, fake_settings
):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    companies = [_lead(1, email=None)]
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.discover_companies", _make_fake_discover(companies)
    )
    monkeypatch.setattr("worksearcher.outreach.pipeline.extract_email", _make_fake_extract())
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.get_connection", lambda path: sqlite3.connect(db_path)
    )

    notified = []

    async def fake_send_outreach_digest(companies, config):
        notified.extend(companies)
        return True

    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.send_outreach_digest", fake_send_outreach_digest
    )

    await run_outreach_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()

    assert count == 1
    assert notified == []


@pytest.mark.asyncio
async def test_outreach_pipeline_dedupes_same_company_within_batch(
    tmp_path, monkeypatch, fake_settings
):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    # Two Overpass elements (e.g. a node and a way) can represent the same
    # business. Both are unseen when discovered, so INSERT OR IGNORE alone
    # would only dedupe on persistence — it wouldn't stop the WhatsApp digest
    # from listing the same company twice in the SAME message. Assert on the
    # notified list, not just the DB row count, or this test can't tell the
    # difference between the pipeline's own dedup and the DB's PRIMARY KEY
    # silently collapsing rows underneath it.
    same_a = _lead(1)
    same_b = _lead(1)  # identical fingerprint (same name + website)
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.discover_companies",
        _make_fake_discover([same_a, same_b]),
    )
    monkeypatch.setattr("worksearcher.outreach.pipeline.extract_email", _make_fake_extract())
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.get_connection", lambda path: sqlite3.connect(db_path)
    )

    notified = []

    async def fake_send_outreach_digest(companies, config):
        notified.extend(companies)
        return True

    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.send_outreach_digest", fake_send_outreach_digest
    )

    await run_outreach_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()

    assert count == 1
    assert len(notified) == 1


@pytest.mark.asyncio
async def test_outreach_pipeline_marks_only_sent_companies_notified(
    tmp_path, monkeypatch, fake_settings
):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    overflow = fake_settings.OUTREACH_MAX_COMPANIES_PER_MESSAGE + 5
    companies = [_lead(i) for i in range(overflow)]
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.discover_companies", _make_fake_discover(companies)
    )
    monkeypatch.setattr("worksearcher.outreach.pipeline.extract_email", _make_fake_extract())
    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.get_connection", lambda path: sqlite3.connect(db_path)
    )

    async def fake_send_outreach_digest(companies, config):
        return True

    monkeypatch.setattr(
        "worksearcher.outreach.pipeline.send_outreach_digest", fake_send_outreach_digest
    )

    await run_outreach_pipeline(fake_settings)

    conn = sqlite3.connect(db_path)
    notified_count = conn.execute("SELECT COUNT(*) FROM companies WHERE notified=1").fetchone()[0]
    unnotified_count = conn.execute("SELECT COUNT(*) FROM companies WHERE notified=0").fetchone()[0]
    conn.close()

    assert notified_count == fake_settings.OUTREACH_MAX_COMPANIES_PER_MESSAGE
    assert unnotified_count == 5


@pytest.mark.asyncio
async def test_outreach_pipeline_skips_when_coordinates_not_configured(monkeypatch, fake_settings):
    fake_settings.OUTREACH_LAT = None

    called = False

    async def discover(config):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("worksearcher.outreach.pipeline.discover_companies", discover)

    await run_outreach_pipeline(fake_settings)

    assert called is False
