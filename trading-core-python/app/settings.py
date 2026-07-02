from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    etoro_api_base_url: str = "https://api.example-etoro.local"
    etoro_api_key: str = "replace_me"
    etoro_account_id: str = "replace_me"
    users_config_api_url: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

