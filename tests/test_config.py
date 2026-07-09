from worksearcher.config import Settings


def _make_settings(**overrides) -> Settings:
    return Settings(
        META_PHONE_NUMBER_ID="123456789",
        META_ACCESS_TOKEN="fake_token",
        META_RECIPIENT_PHONE="521234567890",
        **overrides,
    )


def test_outreach_radius_defaults_to_80km():
    assert _make_settings().OUTREACH_RADIUS_KM == 80


def test_outreach_lat_lon_default_to_none():
    settings = _make_settings()
    assert settings.OUTREACH_LAT is None
    assert settings.OUTREACH_LON is None


def test_outreach_contact_paths_default_list():
    assert _make_settings().outreach_contact_paths_list == [
        "/contacto",
        "/trabaja-con-nosotros",
        "/bolsa-de-trabajo",
        "/careers",
        "/rh",
    ]


def test_outreach_max_companies_defaults():
    settings = _make_settings()
    assert settings.OUTREACH_MAX_COMPANIES_PER_RUN == 100
    assert settings.OUTREACH_MAX_COMPANIES_PER_MESSAGE == 30
