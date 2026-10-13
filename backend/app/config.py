"""Central configuration — everything comes from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://pldhe:pldhe_secret@localhost:5432/pldhe"

    VAPI_API_KEY: str = ""
    VAPI_ASSISTANT_ID: str = ""
    VAPI_PHONE_NUMBER_ID: str = ""

    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/pldhe-helpline-dispatch"
    HELPLINE_NUMBER: str = "0800-78643"

    AUDIO_STORAGE_DIR: str = "/app/audio_storage"


settings = Settings()
