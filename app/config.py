from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    admin_password: str = "admin123"

    chroma_db_path: str = "/app/chroma_db"
    documents_path: str = "/app/documents"

    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    claude_model: str = "claude-sonnet-4-6"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    retrieval_k: int = 15

    class Config:
        env_file = ".env"


settings = Settings()
