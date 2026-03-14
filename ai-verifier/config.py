from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    RATE_LIMIT: str = "10/minute"
    MIN_DESCRIPTION_LENGTH: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
