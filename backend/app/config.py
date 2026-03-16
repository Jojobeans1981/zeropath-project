from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./zeropath.db"
    anthropic_api_key: str = ""
    jwt_secret: str = "change-me"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    redis_url: str = "redis://localhost:6379/0"
    scan_workdir: str = "/tmp/zeropath-scans"
    cors_origins: str = "http://localhost:3000"
    port: int = 8000
    repo_encryption_key: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
