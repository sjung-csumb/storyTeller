# app/models/schemas/agent.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
class BaseSchema(BaseModel):
 """기본 스키마 클래스"""
 class Config:
    from_attributes = True


# ----
# 채팅 관련 스키마를 정의합니다.
# ----
class ChatRequest(BaseSchema):
    """채팅 요청 스키마"""
    query: str = Field(..., description="사용자 질문")
    session_id: Optional[str] = Field(None, description="세션 ID")

class ChatResponse(BaseSchema):
    """채팅 응답 스키마"""
    answer: str = Field(..., description="에이전트 답변")
    user_query: Optional[str] = Field(None, description="사용자 질문")
    process_status: Optional[str] = Field(None, description="처리 상태")
    loop_count: Optional[int] = Field(None, description="루프 횟수")


# ----
# 스트림 관련 스키마를 정의합니다.
# ----
class StreamEvent(BaseSchema):
    """스트림 이벤트 기본 스키마"""
    type: str = Field(..., description="이벤트 타입 (token, log, error)")


class TokenStreamEvent(StreamEvent):
    """토큰 스트림 이벤트 스키마"""
    type: str = Field("token", description="이벤트 타입")
    answer: str = Field(..., description="생성된 답변 토큰")

class LogStreamEvent(StreamEvent):
    """로그 스트림 이벤트 스키마"""
    type: str = Field("log", description="이벤트 타입")
    log: str = Field(..., description="로그 메시지")
class ErrorStreamEvent(StreamEvent):
    """에러 스트림 이벤트 스키마"""
    type: str = Field("error", description="이벤트 타입")
    error: str = Field(..., description="에러 메시지")


# ----
# 지식정보 관련 스키마를 정의합니다.
# ----
class AddKnowledgeRequest(BaseSchema):
    """지식 추가 요청 스키마"""
    documents: List[str] = Field(..., description="추가할 문서 리스트")
    metadatas: Optional[List[Dict[str, Any]]] = Field(None, description="문서별 메타데이터 리스트")

class KnowledgeResponse(BaseSchema):
    """지식 작업 응답 스키마"""
    status: str = Field(..., description="상태 (success/error)")
    message: str = Field(..., description="결과 메시지")

class StatsResponse(BaseSchema):
    """지식 베이스 통계 응답 스키마"""
    name: str = Field(..., description="콜렉션 이름")
    count: int = Field(..., description="문서 개수")
    metadata: Optional[Dict[str, Any]] = Field(None, description="콜렉션 메타데이터")