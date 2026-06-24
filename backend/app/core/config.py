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

    # OpenAI API
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-5.1"
    OPENAI_MAX_OUTPUT_TOKENS: int = 8192
    # Comma-separated vector store IDs covering the 9 legal collections (terminology/precedent lookup)
    OPENAI_VECTOR_STORE_IDS: str = ""

    @property
    def openai_vector_store_id_list(self) -> list[str]:
        return [v.strip() for v in self.OPENAI_VECTOR_STORE_IDS.split(",") if v.strip()]

    # CORS - the WordPress site(s) allowed to call this API
    CORS_ORIGINS: list[str] = ["https://moajamalmaani.com"]

    # WordPress is the only durable file store. Render itself stays stateless:
    # receive a source file URL -> translate -> push the result back to WP -> done.
    WP_BASE_URL: str = ""
    MAX_UPLOAD_SIZE_MB: int = 512

    # RAG knowledge base (backend/knowledge/) used to ground translations in
    # matched-collection samples, on top of the OpenAI vector stores.
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
