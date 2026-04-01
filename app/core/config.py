from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bloom Flower Shop"
    secret_key: str = "secret"
    database_url: str = "sqlite:///./bloom.db"
    app_mode: str = "production"
    free_delivery_from: int = 6000
    base_delivery_cost: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
