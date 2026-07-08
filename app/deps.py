# app/deps.py
from fastapi.params import Depends

from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.vector_service import VectorService
from app.service.embedding_service import EmbeddingService

from app.service.agents.info_extractor_service import InfoExtractorService

def get_vector_repository() -> VectorRepository:
    return ChromaDBRepository()
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
def get_vector_service(
    vector_repo: VectorRepository = Depends(get_vector_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> VectorService:
    return VectorService(
        vector_repository=vector_repo, embedding_service=embedding_service
    )

# [추가] InfoExtractorService 의존성 함수
def get_info_extractor_service() -> InfoExtractorService:
    return InfoExtractorService()
