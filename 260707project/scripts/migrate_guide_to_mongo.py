import os
import sys
import asyncio
import chromadb
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import init_db
from models import ExpertGuide

load_dotenv()

DB_PATH = "data/guide_chroma_db"
COLLECTION_NAME = "childcare_guide"

async def migrate():
    print("1. MongoDB 및 Beanie 초기화...")
    await init_db()
    
    print("2. 기존 ExpertGuide 데이터 초기화 (초기화 후 재등록)...")
    await ExpertGuide.find_all().delete()
    
    print("3. Chroma DB 접속 및 데이터 로드...")
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    try:
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        print(f"[ERROR] Chroma DB 연결 실패: {e}")
        return
        
    data = collection.get()
    docs = data.get("documents", [])
    ids = data.get("ids", [])
    metas = data.get("metadatas", [])
    
    total_docs = len(docs)
    print(f"  - 총 {total_docs}개의 문서를 Chroma DB에서 찾았습니다.")
    
    if total_docs == 0:
        print("  - 마이그레이션 할 데이터가 없습니다.")
        return

    print("4. MongoDB로 마이그레이션 진행...")
    guides_to_insert = []
    for i in range(total_docs):
        # metadatas가 None이거나 해당 인덱스에 없을 수 있으므로 방어 로직 추가
        source_val = "보건복지부 지침서 2013"
        if metas and len(metas) > i and metas[i]:
            source_val = metas[i].get("source", source_val)
            
        guide = ExpertGuide(
            chunk_id=ids[i],
            content=docs[i],
            source=source_val
        )
        guides_to_insert.append(guide)
        
    # 일괄 등록
    await ExpertGuide.insert_many(guides_to_insert)
    
    print(f"\n[SUCCESS] 성공적으로 {len(guides_to_insert)}개의 데이터를 MongoDB(ExpertGuide)로 이관했습니다!")
    
    # 이관 확인
    count = await ExpertGuide.find_all().count()
    print(f"  - 현재 MongoDB 내 ExpertGuide 문서 수: {count}")

if __name__ == "__main__":
    asyncio.run(migrate())
