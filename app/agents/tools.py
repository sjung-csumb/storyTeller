# app/agents/tools.py
from logging import config
from typing import Optional, Dict
from app.service import vector_service
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from app.core.llm import get_solar_chat, get_upstage_embeddings
from app.service.vector_service import VectorService
from app.repository.client.search_client import SerperSearchClient
# 필요한 전역 객체 초기화
embedding_fn = get_upstage_embeddings()
solar_chat = get_solar_chat()
search_client = SerperSearchClient()
@tool
def add_to_medical_qa(content: str, config: RunnableConfig, metadata:
    Optional[Dict] = None) -> str:
    """
    외부에서 찾은 유용한 의학 정보를 내부 지식 저장소(ChromaDB)에 추가합니다.
    """
    print(f"\n[Tool: Add Knowledge] Adding content to DB...")
    print(f" - Content snippet: {content[:100]}...")
    try:
        # Config에서 VectorService를 가져와 사용 (의존성 주입 효과)
        vector_service: VectorService = config["configurable"].get("vector_service")
        if not vector_service:
            return "Error: VectorService not found in config"
        vector_service.add_documents([content], [metadata or {"source":"google_search"}])
        print(f"[Tool: Add Knowledge] Successfully added.")
        return "Successfully added information to knowledge base."
    except Exception as e:
        print(f"[Tool: Add Knowledge] Error: {e}")
        return f"Error adding to knowledge base: {e}"

@tool
def search_medical_qa(query: str, config: RunnableConfig) -> str:
    """
    사용자 질문과 관련된 의학 정보를 내부 DB에서 검색합니다.
    """
    print(f"\n[Tool: Internal DB Search] Query: {query}")
    try:
        vector_service: VectorService = config["configurable"].get("vector_service")
        if not vector_service:
            return "Error: VectorService not found in config"
        qa_list = vector_service.search(query, n_results=5)
 
        print(f"[Tool: Internal DB Search] Found {len(qa_list)} documents.")

        # 검색 결과를 LLM이 이해하기 쉬운 문자열 포맷으로 변환
        context_parts = []
        for i, qa in enumerate(qa_list):
            print(f" - Document {i + 1}: {qa.document[:100]}...")
            context_parts.append(f"Source {i + 1} (Metadata: {qa.metadata}):\n{qa.document}")
    
        return "\n\n".join(context_parts)

    except Exception as e:
        print(f"[Tool: Internal DB Search] Error: {e}")
        return f"Search Error: {e}"
