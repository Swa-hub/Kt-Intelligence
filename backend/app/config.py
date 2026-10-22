from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1/"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_embed_model: str = ""
    # Optional: use a different OpenAI-compatible endpoint for embeddings than
    # for chat completions. Useful when the chat provider (e.g. Groq) doesn't
    # serve embeddings — point embeddings at Nebius/OpenAI, keep chat on Groq.
    embeddings_base_url: str = ""     # empty → use llm_base_url
    embeddings_api_key: str = ""      # empty → use llm_api_key

    # Rate limits — "n/period" strings, e.g. "20/minute". Empty disables.
    rate_limit_llm: str = "20/minute"
    rate_limit_default: str = "120/minute"

    # Simple bearer-token auth. When set, every /api/* request (except /health
    # and the HMAC-verified GitHub webhook) requires:
    #   Authorization: Bearer <API_AUTH_TOKEN>
    # Empty = open mode (fine for localhost demos; set it in production).
    api_auth_token: str = ""

    # Enable response security headers (CSP, X-Frame-Options, etc.).
    # Defaults to on; disable only if you're embedding the API elsewhere.
    security_headers_enabled: bool = True

    backend_host: str = "0.0.0.0"
    backend_port: int = 8010
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    data_dir: str = "./data"
    sqlite_path: str = "./data/kt.db"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 25

    # Optional integrations
    slack_webhook_url: str = ""
    github_webhook_secret: str = ""
    public_base_url: str = ""   # e.g. https://kt-intelligence.vercel.app — used in Slack links

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
