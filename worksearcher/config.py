from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    META_PHONE_NUMBER_ID: str
    META_ACCESS_TOKEN: str
    META_RECIPIENT_PHONE: str
    SEARCH_KEYWORDS: str = "python,backend,cybersecurity,security engineer,SOC,pentester,infosec"
    SCRAPE_INTERVAL_HOURS: int = 4
    MAX_YEARS_EXPERIENCE: int = 3

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.SEARCH_KEYWORDS.split(",")]
