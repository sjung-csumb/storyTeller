# # app/models/entities/__init__.py
# from entities.medical_qa import BaseEntity, MedicalQA

# __all__ = ["BaseEntity", "MedicalQA"]

# from schemas.agent import (
#     BaseSchema,
#     ChatRequest,
#     ChatResponse,
#     StreamEvent,
#     TokenStreamEvent,
#     LogStreamEvent,
#     ErrorStreamEvent,
#     AddKnowledgeRequest,
#     KnowledgeResponse,
#     StatsResponse
# )

# __all__ = [
#     "BaseSchema",
#     "ChatRequest",
#     "ChatResponse",
#     "StreamEvent",
#     "TokenStreamEvent",
#     "LogStreamEvent",
#     "ErrorStreamEvent",
#     "AddKnowledgeRequest",
#     "KnowledgeResponse",
#     "StatsResponse"
# ]

# from .entities import BaseEntity, MedicalQA
# from .schemas import (
#     BaseSchema,
#     AddKnowledgeRequest,
#     KnowledgeResponse,
#     StatsResponse,
#     ChatRequest,
#     ChatResponse,
#     StreamEvent,
#     TokenStreamEvent,
#     LogStreamEvent,
#     ErrorStreamEvent
# )
# __all__ = [
#     "BaseEntity",
#     "MedicalQA",
#     "BaseSchema",
#     "AddKnowledgeRequest",
#     "KnowledgeResponse",
#     "StatsResponse",
#     "ChatRequest",
#     "ChatResponse",
#     "StreamEvent",
#     "TokenStreamEvent",
#     "LogStreamEvent",
#     "ErrorStreamEvent"
# ]

# app/models/__init__.py 

# 1. 파일 구조가 app/models/entities.py, app/models/schemas.py 인 경우
from .entities.medical_qa import BaseEntity, MedicalQA
from .schemas.agent import (
    BaseSchema,
    AddKnowledgeRequest,
    KnowledgeResponse,
    StatsResponse,
    ChatRequest,
    ChatResponse,
    StreamEvent,
    TokenStreamEvent,
    LogStreamEvent,
    ErrorStreamEvent
)

# 2. 만약 파일 구조가 app/models/entities/medical_qa.py 처럼 폴더 구조라면 아래처럼 수정
# from .entities.medical_qa import BaseEntity, MedicalQA

__all__ = [
    "BaseEntity",
    "MedicalQA",
    "BaseSchema",
    "AddKnowledgeRequest",
    "KnowledgeResponse",
    "StatsResponse",
    "ChatRequest",
    "ChatResponse",
    "StreamEvent",
    "TokenStreamEvent",
    "LogStreamEvent",
    "ErrorStreamEvent"
]