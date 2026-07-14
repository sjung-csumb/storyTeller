import asyncio
import sqlite3
import json
import os
import sys

# 상위 디렉토리(프로젝트 루트)의 모듈을 임포트할 수 있도록 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db
from models import Child, FairyTale, Feedback

async def migrate():
    # 1. MongoDB 초기화 (Beanie)
    await init_db()
    
    # 혹시 기존 마이그레이션 흔적이 있다면 초기화할지 묻지 않고 덮어씌우는 대신,
    # 여기서는 단순 추가를 방지하기 위해 콜렉션을 비웁니다 (새로 이주하는 상황이므로)
    print("기존 MongoDB 컬렉션 초기화 중...")
    await Child.delete_all()
    await FairyTale.delete_all()
    await Feedback.delete_all()

    # 2. SQLite 연결
    sqlite_db_path = os.path.join("backup_db", "fairy_tale.db")
    if not os.path.exists(sqlite_db_path):
        print(f"❌ 백업된 SQLite DB를 찾을 수 없습니다: {sqlite_db_path}")
        return

    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # SQLite ID -> MongoDB ObjectId 맵핑 저장용 딕셔너리
    child_id_map = {}
    fairytale_id_map = {}

    print("마이그레이션 시작...")

    # --- 1. Child 마이그레이션 ---
    cursor.execute("SELECT * FROM child")
    children_rows = cursor.fetchall()
    
    for row in children_rows:
        child_doc = Child(
            name=row["name"],
            birth_year=row["birth_year"],
            gender=row["gender"],
            created_at=row["created_at"]
        )
        await child_doc.insert()
        child_id_map[row["id"]] = child_doc.id
        
    print(f"Child 데이터 {len(children_rows)}건 이관 완료")

    # --- 2. FairyTale 마이그레이션 ---
    cursor.execute("SELECT * FROM fairytale")
    fairytale_rows = cursor.fetchall()
    
    for row in fairytale_rows:
        # SQLite에 있던 content_json을 실제 파이썬 리스트/딕셔너리로 변환
        raw_json = row["content_json"]
        try:
            content_list = json.loads(raw_json)
        except Exception:
            content_list = []

        # child 외래키 맵핑
        mongo_child_id = child_id_map.get(row["child_id"])
        if not mongo_child_id:
            continue

        fairytale_doc = FairyTale(
            title=row["title"],
            appearance=row["appearance"],
            personality=row["personality"],
            place=row["place"],
            time_period=row["time_period"],
            mood=row["mood"],
            problem_situation=row["problem_situation"],
            language=row["language"] if "language" in row.keys() else "ko",
            content=content_list,  # JSON 데이터 내장!
            child_id=mongo_child_id,
            created_at=row["created_at"]
        )
        await fairytale_doc.insert()
        fairytale_id_map[row["id"]] = fairytale_doc.id

    print(f"FairyTale 데이터 {len(fairytale_rows)}건 이관 완료")

    # --- 3. Feedback 마이그레이션 ---
    cursor.execute("SELECT * FROM feedback")
    feedback_rows = cursor.fetchall()
    
    for row in feedback_rows:
        mongo_ft_id = fairytale_id_map.get(row["fairy_tale_id"])
        if not mongo_ft_id:
            continue
            
        feedback_doc = Feedback(
            rating=row["rating"],
            fairy_tale_id=mongo_ft_id,
            created_at=row["created_at"]
        )
        await feedback_doc.insert()
        
    print(f"Feedback 데이터 {len(feedback_rows)}건 이관 완료")
    print("모든 마이그레이션 작업이 성공적으로 끝났습니다!")

if __name__ == "__main__":
    asyncio.run(migrate())
