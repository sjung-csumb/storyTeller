import os
from sqlmodel import SQLModel, create_engine, Session

# SQLite 데이터베이스 파일 경로 설정
DATABASE_FILE = "fairy_tale.db"
database_url = f"sqlite:///{DATABASE_FILE}"

# echo=True 설정 시 생성되는 모든 SQL 쿼리가 콘솔에 출력되어 디버깅에 용이합니다.
engine = create_engine(database_url, echo=True, connect_args={"check_same_thread": False})


def init_db():
    """데이터베이스 테이블을 생성합니다."""
    # models.py에서 정의된 테이블 모델들을 임포트하여 metadata에 등록되도록 합니다.
    import models  # noqa: F401
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI 등에서 의존성 주입(Dependency)으로 사용할 세션 제너레이터입니다."""
    with Session(engine) as session:
        yield session
