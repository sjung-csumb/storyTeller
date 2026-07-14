from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import Field
from beanie import Document, PydanticObjectId

class Child(Document):
    name: str
    birth_year: int
    gender: str  # "남자", "여자", "선택 안함" 등
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "children"


class FairyTale(Document):
    title: str
    appearance: str = Field(description="주인공의 외형")
    personality: str = Field(description="주인공의 성격")
    place: str = Field(description="장소")
    time_period: str = Field(description="시대")
    mood: str = Field(description="분위기")
    problem_situation: str = Field(description="교정이 필요한 문제 상황")
    language: str = Field(default="ko", description="동화가 생성된 언어 (ko 또는 en)")
    status: str = Field(default="draft", description="진행 상태: draft / published")
    draft_text: Optional[str] = Field(default=None, description="LLM이 생성한 최신 텍스트 원본 보관용")
    guide_text: Optional[str] = Field(default=None, description="RAG에서 검색한 전문가 지침")
    
    # MongoDB의 장점: JSON 문자열 대신 실제 리스트/딕셔너리 구조 그대로 내장 가능
    content: List[Dict[str, Any]] = Field(default_factory=list, description="페이지별 내용 및 삽화 이미지")
    
    # 참조형 (SQL의 Foreign Key 역할)
    child_id: PydanticObjectId
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "fairytales"


class Feedback(Document):
    rating: int = Field(description="동화 만족도 별점 (1~5)")
    fairy_tale_id: PydanticObjectId
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "feedbacks"

class ExpertGuide(Document):
    """
    보건복지부 영유아 문제행동지도 지침서 등 전문가 솔루션 텍스트 저장 모델
    추후 기능 확장 및 중앙 관리를 위해 Chroma DB의 내용을 미러링합니다.
    """
    chunk_id: str
    content: str
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

