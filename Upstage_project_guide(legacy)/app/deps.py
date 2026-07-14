# app/deps.py
from fastapi.params import Depends

from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.vector_service import VectorService
from app.service.embedding_service import EmbeddingService

#5.2 InfoExtractor
from app.service.agents.info_extractor_service import InfoExtractorService
#5.3 KnowledgeAugmentor
from app.service.agents.knowledge_augmentor_service import KnowledgeAugmentorService
#5.4 AnswerGenService
from app.service.agents.answer_gen_service import AnswerGenService
#5.5 AgentService
from app.service.agent_service import AgentService


from app.repository.vector.vector_repo import VectorRepository


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
# [추가] KnowledgeAugmentorService 의존성 함수
def get_knowledge_augmentor_service() -> KnowledgeAugmentorService:
    return KnowledgeAugmentorService()
# [추가] AnswerGenService 의존성 함수
def get_answer_gen_service() -> AnswerGenService:
 return AnswerGenService()
# [추가] AgentService 의존성 함수
def get_agent_service(
    vector_service: VectorService = Depends(get_vector_service),
    info_extractor_service: InfoExtractorService = Depends(get_info_extractor_service),
    knowledge_augmentor_service: KnowledgeAugmentorService = Depends(get_knowledge_augmentor_service),
    answer_gen_service: AnswerGenService = Depends(get_answer_gen_service),
) -> AgentService:
    return AgentService(
        vector_service=vector_service,
        info_extractor_service=info_extractor_service,
        knowledge_augmentor_service=knowledge_augmentor_service,
        answer_gen_service=answer_gen_service,
    )