from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    # Ordem da cadeia de provedores de IA (ver PROVIDER_FACTORIES). Cada um
    # só entra se a chave dele estiver configurada. Todos no plano gratuito.
    ai_provider: str = "gemini,groq,openrouter"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    # Segundo degrau, quando o principal falha (429 de cota, 503, timeout).
    # Vazio desliga.
    gemini_fallback_model: str | None = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: int = 30
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    openrouter_api_key: str | None = None
    # Só modelos com sufixo :free; outro valor tira o OpenRouter da cadeia.
    openrouter_model: str = "nvidia/nemotron-3.5-super-vl:free"
    ai_fallback_timeout_seconds: int = 20
    rate_limit_enabled: bool = True
    # Só ligue atrás de um proxy que sobrescreve o X-Forwarded-For (a Vercel faz isso).
    trust_proxy_headers: bool = False
    sql_echo: bool = False
    # Em serverless cada instância é efêmera: quem faz o pool é o banco.
    db_null_pool: bool = False

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Provedores entregam postgres://, que o SQLAlchemy não aceita."""
        if value.startswith("postgres://"):
            return "postgresql://" + value.removeprefix("postgres://")
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """O .env guarda as origens separadas por vírgula; aqui vira lista."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
