import httpx
import pytest
import respx

from worksearcher.outreach.discovery import discover_companies


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
