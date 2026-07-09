import httpx
import pytest
import respx

from worksearcher.core.models import Company
from worksearcher.outreach.discovery import discover_companies
from worksearcher.outreach.email_extractor import extract_email


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
async def test_discover_companies_raises_without_coordinates(fake_settings):
    fake_settings.OUTREACH_LAT = None
    with pytest.raises(ValueError):
        await discover_companies(fake_settings)


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
