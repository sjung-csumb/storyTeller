# API 서버가 에이전트와 소통하는 창구입니다. 사용자의 질문을 super_graph에 전달하고 결과를
# 스트리밍합니다.
# 5.1. 환경 설정 및 초기화 (Imports & init)
# app/service/agent_service.py
import os
from typing import List, Dict, Any
from openai import OpenAI # openai==1.52.2
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from app.exceptions import AgentNotFoundException
from app.service.vector_service import VectorService
from app.service.agents.info_extractor_service import InfoExtractorService
from app.service.agents.knowledge_augmentor_service import KnowledgeAugmentorService
from app.service.agents.answer_gen_service import AnswerGenService
# 앞서 만든 app/agents/__init__.py를 통해 메인 그래프를 import 합니다.
from app.agents import super_graph
# [환경 설정]
# .env 파일이 있으면 로드하고, 없으면 주입된 환경변수를 사용합니다.
load_dotenv(override=False)
class AgentService:
    def __init__(
        self,
        vector_service: VectorService,
        info_extractor_service: InfoExtractorService,
        knowledge_augmentor_service: KnowledgeAugmentorService,
        answer_gen_service: AnswerGenService
    ):
        api_key = os.getenv("UPSTAGE_API_KEY")
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key, base_url="https://api.upstage.ai/v1")
        self.vector_service = vector_service
        
        # 의존성 주입 (Sub-services)
        self.info_extractor_service = info_extractor_service
        self.knowledge_augmentor_service = knowledge_augmentor_service
        self.answer_gen_service = answer_gen_service


    # 5.2. 지식 관리 (add_knowledge, get_knowledge_stats)
    # 에이전트 실행과는 별개로, Vector DB를 관리하는 헬퍼 함수들입니다. 사용자가 문서를 업로드하거나
    # 현재 상태를 확인할 때 사용됩니다.

    def add_knowledge(
        self, documents: List[str], metadatas: List[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        지식 베이스(Vector DB)에 새로운 정보를 추가합니다.
        """
        try:
        # documents와 metadatas를 사용하여 MedicalQA 리스트를 생성하는 방식으로 확장 가능하지만
        # 현재는 단순 전달 구조 유지. 필요시 엔티티 변환 로직 추가 가능.
            self.vector_service.add_documents(documents, metadatas)
            return {
            "status": "success",
            "message": f"Added {len(documents)} documents to knowledge base",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to add documents: {str(e)}"}
    
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """
        현재 구축된 지식 베이스의 상태(문서 수 등)를 조회합니다.
        """
        return self.vector_service.get_collection_info()
    
    
    # 5.3. 에이전트 실행 (run_agent)
    # 에이전트 서비스를 실행하는 함수를 정의합니다.
    def run_agent(self, inputs: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
        """
        에이전트를 실행하고 최종 결과를 반환합니다. (디버깅/테스트용)
        """
        # session_id가 있으면 LangGraph의 Checkpointer가 이전 대화(answer_logs)를 불러오므로
        # 여기서는 새로운 user_query만 명확히 넣어줍니다.
        full_inputs = {
            "user_query": inputs["user_query"],
            "answer_logs": [HumanMessage(content=inputs["user_query"])],
            "build_logs": [],
            "augment_logs": [],
            "extract_logs": [],
            "loop_count": 0
        }

        # 그래프 내 노드들이 사용할 서비스(도구)들을 Config에 주입
        config = {
            "configurable": {
            "vector_service": self.vector_service,
            "info_extractor_service": self.info_extractor_service,
            "knowledge_augmentor_service": self.knowledge_augmentor_service,
            "answer_gen_service": self.answer_gen_service,
            }
        }
        if session_id:
            config["configurable"]["thread_id"] = session_id
        
        # Super Graph 실행
        result = super_graph.invoke(full_inputs, config=config)
        return result
    # 5.4. 실시간 스트리밍 (stream_agent)
    # 에이전트 서비스를 스트리밍 형태로 실행하는 함수를 정의합니다.
    async def stream_agent(self, inputs: Dict[str, Any], session_id: str = None):
        """
        에이전트를 스트리밍 모드로 실행합니다.
        LangGraph v2의 astream_events를 사용하여 토큰 단위 생성을 지원합니다.
        """
        full_inputs = {
            "user_query": inputs["user_query"],
            "answer_logs": [HumanMessage(content=inputs["user_query"])],
            "build_logs": [],
            "augment_logs": [],
            "extract_logs": [],
            "loop_count": 0
        }

        config = {
            "configurable": {
                "vector_service": self.vector_service,
                "info_extractor_service": self.info_extractor_service,
                "knowledge_augmentor_service": self.knowledge_augmentor_service,
                "answer_gen_service": self.answer_gen_service,
            }
        }
        if session_id:
            config["configurable"]["thread_id"] = session_id
        # astream_events: 그래프 내부에서 일어나는 모든 이벤트(LLM 토큰 생성, 도구 호출 등)를 스트리밍
        async for event in super_graph.astream_events(full_inputs, config=config, version="v2"):
            yield event
