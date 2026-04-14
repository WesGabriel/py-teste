from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    kb_url: str

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str
    llm_base_url: str = "https://api.openai.com/v1"

    memory_store: str = "memory"

    host: str = "0.0.0.0"
    port: int = 8000

    relevance_threshold: float = 0.15
    kb_cache_ttl: int = 300
    top_n_sections: int = 3


def get_settings() -> Settings:
    return Settings()
