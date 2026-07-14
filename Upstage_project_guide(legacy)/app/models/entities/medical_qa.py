# 1. Entity 정의
# Vector DB(ChromaDB) 지식 데이터의 원형입니다. Pydantic을 활용하여 심플하게 정의합니다.

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class BaseEntity(BaseModel):
 """기본 엔티티 클래스"""
class Config:
        from_attributes = True


class MedicalQA(BaseEntity):
 """
 의료 지식 베이스의 개별 문서를 나타내는 엔티티
 """
 id: Optional[str] = Field(None, description="문서 식별자")
 document: str = Field(..., description="문서 본문 내용 (예: Q: ..., A: ...)")
 metadata: Dict[str, Any] = Field(default_factory=dict, description="추가메타데이터 (source, domain 등 포함)")
