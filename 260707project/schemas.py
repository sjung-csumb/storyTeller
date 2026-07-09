from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChildCreate(BaseModel):
    name: str
    age: int
    gender: str

class ChildRead(BaseModel):
    id: int
    name: str
    age: int
    gender: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class FairyTaleCreate(BaseModel):
    appearance: str = Field(..., description="주인공 외형")
    personality: str = Field(..., description="주인공 성격")
    place: str = Field(..., description="장소")
    time_period: str = Field(..., description="시대")
    mood: str = Field(..., description="분위기")
    problem_situation: str = Field(..., description="교정이 필요한 문제 상황")
    language: str = Field(default="ko", description="동화 생성 언어 (ko 또는 en)")

class FairyTaleRead(BaseModel):
    id: int
    title: str
    appearance: str
    personality: str
    place: str
    time_period: str
    mood: str
    problem_situation: str
    language: str
    content_json: str
    child_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)

class FeedbackRead(BaseModel):
    id: int
    rating: int
    fairy_tale_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
