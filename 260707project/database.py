import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

async def init_db():
    """MongoDB 클라이언트와 Beanie ODM을 초기화합니다."""
    # Motor 클라이언트 생성
    client = AsyncIOMotorClient(MONGODB_URI)
    
    # 데이터베이스 선택
    db = client.get_database("fairy_tale_db")
    
    # 등록할 문서 모델들 임포트
    from models import Child, FairyTale, Feedback, ExpertGuide
    
    # Beanie 초기화
    await init_beanie(
        database=db,
        document_models=[Child, FairyTale, Feedback, ExpertGuide]
    )
