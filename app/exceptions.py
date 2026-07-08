# app/exceptions.py
from typing import Any, Dict, Optional

class BaseAppException(Exception):
    """애플리케이션의 모든 커스텀 예외의 기본 클래스"""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
class AgentException(BaseAppException):
    """에이전트 실행 및 로직 관련 예외"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)
class KnowledgeBaseException(BaseAppException):
    """지식 베이스(벡터 DB) 조작 관련 예외"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)
class ValidationException(BaseAppException):
    """입력 데이터 유효성 검사 실패 시 발생"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code = 400, details=details)