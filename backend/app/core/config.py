from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Moajam Almaani API"
    ENV: str = "production"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str
    API_KEY: str  # shared key used by the WordPress snippet
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "sqlite:///./moajam.db"

    # Anthropic (Claude) API
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_OUTPUT_TOKENS: int = 8192

    # CORS - the WordPress site(s) allowed to call this API
    CORS_ORIGINS: list[str] = ["https://moajamalmaani.com"]

    # WordPress is the only durable file store. Render itself stays stateless:
    # receive a source file URL -> translate -> push the result back to WP -> done.
    WP_BASE_URL: str = ""
    # WordPress Application Password (Users -> Profile -> Application Passwords),
    # used for source-file uploads via the core /wp-json/wp/v2/media route.
    # Set these in .env only - never commit real values.
    WP_USER: str = ""
    WP_APP_PASSWORD: str = ""
    MAX_UPLOAD_SIZE_MB: int = 512

    # RAG knowledge base (backend/knowledge/) used to ground translations in
    # matched-collection samples (keyword-based retrieval, no embeddings).
    KNOWLEDGE_DIR: str = "knowledge"

    # Invoicing
    COMPANY_NAME: str = "Moajam Almaani"
    COMPANY_NAME_AR: str = "معجم المعاني"
    COMPANY_EMAIL: str = "info@moajamalmaani.com"
    COMPANY_ADDRESS: str = ""
    CURRENCY: str = "EGP"
    DEFAULT_TRANSLATION_PRICE: float = 0.0
    ARABIC_FONT_PATH: str = "app/assets/fonts/NotoNaskhArabic-Regular.ttf"

    # Accounting - codes used when auto-posting invoice payments to the ledger
    ACCOUNTING_CASH_ACCOUNT_CODE: str = "1000"
    ACCOUNTING_REVENUE_ACCOUNT_CODE: str = "4000"

    # Payments (optional, disabled unless keys provided)
    PAYMOB_API_KEY: str | None = None
    PAYMOB_INTEGRATION_ID: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
