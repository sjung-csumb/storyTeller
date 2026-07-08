# app/main.py
# 1. FastAPI 앱 초기화 (app/main.py)
# 모듈들을 import하고 서버가 시작되거나 종료될 때 실행할 로직을 Lifespan에 정의합니다.
# 이 Lifespan을 반영한 FastAPI 앱을 초기화 합니다.

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio
from app.api.route.agent_routers import router as agent_router
from app.core.seed import seed_data_if_empty
from app.exceptions import AgentException, KnowledgeBaseException,ValidationException

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 실행
    # 시딩 작업은 시간이 걸릴 수 있으므로 메인 스레드를 막지 않도록
    # 별도의 스레드 실행기(Executor)에서 백그라운드로 실행합니다.
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, seed_data_if_empty)
    yield # 애플리케이션 실행 중...


# FastAPI 앱 초기화
app = FastAPI(lifespan=lifespan)


# 2. Global Exception Handler 정의 (app/main.py)
# Step 12에서 정의한 커스텀 예외들이 발생했을 때, 클라이언트에게 보낼 JSON 응답을 정의합니다.
# 커스텀 예외들 외에도, 기타 기본 예외 처리도 적용합니다.
@app.exception_handler(AgentException)
async def agent_exception_handler(request: Request, exc: AgentException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "AgentException",
            "message": exc.message,
            "details": exc.details
        },
    )
@app.exception_handler(KnowledgeBaseException)
async def knowledge_base_exception_handler(request: Request, exc: KnowledgeBaseException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "KnowledgeBaseException",
            "message": exc.message,
            "details": exc.details
        },
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "ValidationException",
            "message": exc.message,
            "details": exc.details
        },
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "ValueError", "message": str(exc), "details": {}},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTPException", "message": exc.detail, "details": {}},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
 # 예상치 못한 모든 에러를 잡아서 500 Internal Server Error로 처리합니다.
 return JSONResponse(
    status_code=500,
    content={
        "error": "InternalServerError",
        "message": "An unexpected error occurred",
        "details": {"type": exc.__class__.__name__, "info": str(exc)}
    },
 )
# 3. 라우터 연결 및 서버 실행 (app/main.py)
app.include_router(agent_router)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
