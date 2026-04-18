from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://hiddenalerts:dev_password@localhost:5432/hiddenalerts"
    database_url_sync: str = "postgresql://hiddenalerts:dev_password@localhost:5432/hiddenalerts"

    # Application
    app_env: str = "development"
    debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_interval_hours: int = 6
    default_polling_minutes: int = 60

    # AI (Milestone 2)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Email (Milestone 2+)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_recipients: str = ""

    # Auth (Milestone 2)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 days for MVP

    # Admin user seeding (Milestone 2)
    admin_email: str = ""
    admin_password: str = ""  # plain-text; hashed at migration time

    # AI processing controls (Milestone 2)
    ai_processing_enabled: bool = True
    ai_max_retries: int = 3
    ai_retry_delay_seconds: float = 2.0


settings = Settings()
