from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from beanie import PydanticObjectId

class ChildCreate(BaseModel):
    name: str
    birth_year: int
    gender: str

class ChildRead(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    name: str
    birth_year: int
    gender: str
    created_at: datetime
    
    class Config:
        from_attributes = True
        populate_by_name = True

class FairyTaleCreate(BaseModel):
    appearance: str = Field(..., description="주인공 외형")
    personality: str = Field(..., description="주인공 성격")
    place: str = Field(..., description="장소")
    time_period: str = Field(..., description="시대")
    mood: str = Field(..., description="분위기")
    problem_situation: str = Field(..., description="교정이 필요한 문제 상황")
    language: str = Field(default="ko", description="동화 생성 언어 (ko 또는 en)")

class FairyTaleRead(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    title: str
    appearance: str
    personality: str
    place: str
    time_period: str
    mood: str
    problem_situation: str
    language: str
    guide_text: Optional[str] = None
    content: List[Dict[str, Any]]
    child_id: PydanticObjectId
    created_at: datetime
    
    class Config:
        from_attributes = True
        populate_by_name = True

class DraftRead(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    title: str
    guide_text: Optional[str] = None
    pages: List[Dict[str, str]]
    
    class Config:
        from_attributes = True
        populate_by_name = True

class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)

class FeedbackRead(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    rating: int
    fairy_tale_id: PydanticObjectId
    created_at: datetime
    
    class Config:
        from_attributes = True
        populate_by_name = True
