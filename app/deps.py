#app/deps.py
from fastapi.params import Depends

from app.service.embbedding_service import EmbeddingService

def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
