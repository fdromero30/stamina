from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    users_config_api_url: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

