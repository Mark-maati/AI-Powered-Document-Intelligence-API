from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "Document Intelligence API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    DATABASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"

    RATE_LIMIT: str = "10/minute"
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx"})

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
