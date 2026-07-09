from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    age: int = Field(nullable=False)
    gender: str = Field(nullable=False)  # "남자", "여자", "선택 안함" 등
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    fairy_tales: List["FairyTale"] = Relationship(back_populates="child")


class FairyTale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(nullable=False)
    appearance: str = Field(nullable=False, description="주인공의 외형")
    personality: str = Field(nullable=False, description="주인공의 성격")
    place: str = Field(nullable=False, description="장소")
    time_period: str = Field(nullable=False, description="시대")
    mood: str = Field(nullable=False, description="분위기")
    problem_situation: str = Field(
        nullable=False,
        description="교정이 필요한 문제 상황 (예: 양치질을 하기 싫어함)"
    )
    language: str = Field(default="ko", description="동화가 생성된 언어 (ko 또는 en)")
    
    # 동화의 구체적인 내용(페이지별 텍스트, 이미지 URL 등)을 JSON 문자열로 저장
    # 예: [{"page": 1, "text": "...", "image_url": "..."}, ...]
    content_json: str = Field(nullable=False, description="페이지별 내용 및 삽화 이미지 경로가 포함된 JSON")
    
    child_id: int = Field(foreign_key="child.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    child: Child = Relationship(back_populates="fairy_tales")
    feedbacks: List["Feedback"] = Relationship(back_populates="fairy_tale")


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rating: int = Field(nullable=False, description="동화 만족도 별점 (1~5)")
    fairy_tale_id: int = Field(foreign_key="fairytale.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    fairy_tale: FairyTale = Relationship(back_populates="feedbacks")
