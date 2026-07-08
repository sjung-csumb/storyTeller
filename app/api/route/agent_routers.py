from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core.logger import logger
from app.models import (
    AddKnowledgeRequest,
    KnowledgeResponse,
    StatsResponse,
    ChatRequest,
    ChatResponse,
    TokenStreamEvent,
    LogStreamEvent,
    ErrorStreamEvent
)
from app.exceptions import AgentException, KnowledgeBaseException
from app.deps import get_agent_service
from app.service.agent_service import AgentService
from app.core.seed import get_seed_status

# 라우터 설정: 프리픽스(/agent)와 태그 설정
router = APIRouter(prefix="/agent", tags=["agent"])

# 1. 설정 및 기본 유틸리티 (app/api/route/agent_routers.py)
# 이 부분은 라우터를 초기화하고, 서버나 데이터 시딩 상태를 확인하는 가벼운 기능들입니다.
# ● APIRouter: /agent로 시작하는 모든 URL을 이 파일에서 처리하도록 묶어줍니다
# ● /seed-status: 서버 시작 시 대용량 데이터가 잘 들어갔는지 확인하는 용도입니다.
@router.get("/health")
async def health_check():
    """서버가 살아있는지 확인하는 헬스 체크용 엔드포인트입니다."""
    return {"status": "healthy", "message": "Agent service is running"}
@router.get("/seed-status")
async def seed_status():
    """초기 데이터 시딩(Seeding) 진행 상황을 확인합니다."""
    return get_seed_status()

# 2. 일반 채팅 (app/api/route/agent_routers.py)
# 결과를 한 번에 기다렸다가 받는 전통적인 방식의 API입니다.

# ● run_agent: 에이전트의 사고 과정(생각 -> 도구 사용 -> 답변)이 끝날 때까지 블로킹됩니다.
# ● 결과 추출: answer_logs 리스트의 가장 마지막 메시지가 최종 답변이므로 이를 추출하여
# 반환합니다.

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, agent_service: AgentService = Depends(get_agent_service)
):
    try:
        # 1. 에이전트 실행 (결과가 나올 때까지 기다림)
        inputs = {"user_query": request.query, "process_status": "start"}
        result = agent_service.run_agent(inputs, session_id=request.session_id)
        
        # 2. 결과 처리
        serializable_result = {"answer": ""}
        
        # 대화 기록 중 마지막 AI 메시지를 찾아 최종 답변으로 설정
        answer_logs = result.get("answer_logs", [])
        if answer_logs:
            last_msg = answer_logs[-1]
        if getattr(last_msg, 'type', '') == 'ai':
            serializable_result["answer"] = last_msg.content
        
        # 메타데이터(상태, 루프 횟수 등) 추가
        for k in ["user_query", "process_status", "loop_count"]:
            if k in result:
                serializable_result[k] = result[k]
        return serializable_result
    
    # 커스텀 예외 처리: 미리 정의한 에러가 발생하면 그대로 전달
    except (AgentException, KnowledgeBaseException) as e:
        raise e
    except Exception as e:
        raise AgentException(f"Chat processing failed: {str(e)}")
    
# 3. 스트리밍 채팅 (app/api/route/agent_routers.py)
# 이 부분이 가장 복잡하지만 사용자 경험(UX)에 제일 중요합니다. 에이전트의 '생각'과 '답변'을
# 실시간으로 나누어 전송합니다.
# ● current_node: 현재 에이전트가 '생각 중(검색)'인지 '말하는 중(답변)'인지 구분하기 위한
# 변수입니다.
# ● 이벤트 분리:
# ● LogStreamEvent: "검색 중..." 같은 시스템 메시지. 프론트엔드에서 Spinner내에 표시
# ● TokenStreamEvent: 실제 답변 텍스트. 타자기 효과로 표시.
@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest, agent_service: AgentService = Depends(get_agent_service)
):
    async def event_generator():
        try:
            inputs = {"user_query": request.query, "process_status": "start"}
            current_node = "" # 현재 에이전트가 어떤 작업을 하고 있는지 추적

            # LangGraph의 이벤트를 실시간으로 하나씩 받아서 처리
            async for event in agent_service.stream_agent(inputs, session_id=request.session_id):
                kind = event.get("event")
                name = event.get("name", "")

                # 1. 단계별 상태 로그 전송 (LogStreamEvent)
                # Workflow 노드에 진입할 때마다 '검색 중...', '답변 생성 중...' 등의 로그를 보냅니다.
                if kind == "on_chain_start":
                    if name and ("workflow" in name or name == "super_graph"):
                        current_node = name # 현재 단계 업데이트
               
                    if name == "info_extract_agent_workflow":
                        yield f"data: {LogStreamEvent(log='내부 지식 검색중...').model_dump_json(ensure_ascii=False)}\n\n"
                    elif name == "knowledge_augment_workflow":
                        yield f"data: {LogStreamEvent(log='외부 지식 검색 중 (Google Search)...').model_dump_json(ensure_ascii=False)}\n\n"
                    elif name == "answer_gen_agent_workflow":
                        yield f"data: {LogStreamEvent(log='답변 생성중...').model_dump_json(ensure_ascii=False)}\n\n"
                    
                # 2. 도구 사용 로그 전송
                elif kind == "on_tool_start":
                    if event.get("name") == "search_medical_qa":
                        yield f"data: {LogStreamEvent(log='내부 DB 검색실행...').model_dump_json(ensure_ascii=False)}\n\n"
                    elif event.get("name") == "google_search":
                        yield f"data: {LogStreamEvent(log='Google 검색실행...').model_dump_json(ensure_ascii=False)}\n\n"
                
                # 3. 답변 토큰 스트리밍 (TokenStreamEvent)
                elif kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        # [중요 로직] 검색이나 추출 단계에서의 LLM 출력은 사용자에게보여주지 않고(숨김),
                        # 최종 답변 생성 단계('answer_gen')일 때만 토큰을 전송합니다.
                        if current_node not in ["info_extract_agent_workflow","knowledge_augment_workflow"]:
                            yield f"data:{TokenStreamEvent(answer=content).model_dump_json(ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n" # 종료 신호
        except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {ErrorStreamEvent(error=str(e)).model_dump_json(ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# 4. 지식 관리 (app/api/route/agent_routers.py)
# 문서를 추가하거나 삭제하고, 현황을 파악하는 기능입니다
@router.post("/knowledge", response_model=KnowledgeResponse)
async def add_knowledge(
    request: AddKnowledgeRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """문서를 수동으로 추가합니다."""
    try:
        result = agent_service.add_knowledge(
            documents=request.documents, metadatas=request.metadatas
        )
        return KnowledgeResponse(result)
    except (AgentException, KnowledgeBaseException) as e:
        raise e
    except Exception as e:
        raise KnowledgeBaseException(f"Adding knowledge failed: {str(e)}")
    

@router.get("/stats", response_model=StatsResponse)
async def get_knowledge_stats(agent_service: AgentService = Depends(get_agent_service)):
    """현재 저장된 문서 개수 등의 통계를 조회합니다."""
    try:
        stats = agent_service.get_knowledge_stats()
        return StatsResponse(stats)
    except Exception as e:
        raise KnowledgeBaseException(f"Failed to get stats: {str(e)}")
@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: str, agent_service: AgentService = Depends(get_agent_service)
):
    """특정 문서를 ID로 삭제합니다."""
    try:
        agent_service.vector_service.delete_document(doc_id)
        return {"status": "success", "message": f"Document {doc_id} deleted"}
    except Exception as e:
        raise KnowledgeBaseException(f"Deletion failed: {str(e)}")
