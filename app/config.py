from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    evolution_api_url: str = "http://evolution-api:8080"
    evolution_api_key: str
    evolution_instance: str = "whatsapp-bot"

    chroma_db_path: str = "/app/chroma_db"
    documents_path: str = "/app/documents"

    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    claude_model: str = "claude-sonnet-4-6"
    chunk_size: int = 800
    chunk_overlap: int = 100
    retrieval_k: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
