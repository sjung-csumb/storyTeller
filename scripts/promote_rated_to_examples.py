"""
평점 4점 이상 동화를 예시 풀로 승격 (피드백 루프)
==================================================

사용자가 별점 4점 이상을 준 '실제 발행 동화'를 fairytale_examples 예시 풀에 추가한다.
LLM으로 생성한 골든 예시(build_golden_examples.py)보다 '사람이 검증한 실물'이라 예시로서
가치가 높다. 골든 예시와 같은 구조(조건 요약 키 색인 + 본문 메타데이터)로 넣어 호환된다.

동작:
  MongoDB Feedback(rating >= 4) 조회
    → fairy_tale_id 로 FairyTale(발행 동화) 본문 추출 (표지 제외, 페이지 텍스트만)
    → 저장된 mood + Child.birth_year 로 대상연령대/분위기 라벨 구성 (LLM 불필요)
    → fairytale_examples 컬렉션에 upsert (id=rated_<fairy_tale_id> → 재실행해도 중복 없음)

산출물: data/rated_examples.jsonl (승격 기록)
실행:   uv run python scripts/promote_rated_to_examples.py
        (평점이 쌓일 때마다 다시 실행하면 새로 4점 이상 된 동화만 반영됨)
"""
import os
import sys
import json
from datetime import datetime

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv
from kb_retriever import UpstageEmbeddingFunction

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "fairy_tale_db"
DB_PATH = "data/guide_chroma_db"
COLLECTION = "fairytale_examples"
PASSAGE_MODEL = "solar-embedding-1-large-passage"
MIN_RATING = 4
OUT = "data/rated_examples.jsonl"


def age_band_from_birth_year(birth_year) -> str:
    if not birth_year:
        return "3~4세"
    age = datetime.now().year - int(birth_year)
    return "3~4세" if age <= 4 else "5~7세"


def extract_story(content) -> str:
    """FairyTale.content(페이지 배열)에서 표지 제외 본문 텍스트만 이어붙인다."""
    parts = []
    for p in content or []:
        if isinstance(p, dict) and not p.get("is_cover") and p.get("text"):
            parts.append(str(p["text"]).strip())
    return "\n".join(parts)


def main():
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("[ERROR] UPSTAGE_API_KEY 필요")
        return

    # --- MongoDB 연결 ---
    try:
        mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
        mongo.admin.command("ping")
    except Exception as e:
        print(f"[ERROR] MongoDB 연결 실패: {e}")
        return
    db = mongo.get_database(DB_NAME)

    # --- 4점 이상 피드백 → fairy_tale_id (중복 제거, 최고 평점 유지) ---
    best = {}
    for fb in db.feedbacks.find({"rating": {"$gte": MIN_RATING}}):
        fid = fb.get("fairy_tale_id")
        if fid is not None:
            best[fid] = max(best.get(fid, 0), int(fb.get("rating", 0)))
    print(f"[load] 4점 이상 받은 동화: {len(best)}편")
    if not best:
        print("[info] 아직 4점 이상 동화가 없습니다. 평점이 쌓이면 다시 실행하세요.")
        return

    # --- ChromaDB 예시 컬렉션 (골든 예시와 같은 컬렉션에 추가) ---
    client = OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],
                    base_url="https://api.upstage.ai/v1/solar")
    passage_ef = UpstageEmbeddingFunction(client, model_name=PASSAGE_MODEL)
    chroma = chromadb.PersistentClient(path=DB_PATH)
    col = chroma.get_or_create_collection(COLLECTION, embedding_function=passage_ef)

    rows = []
    out_f = open(OUT, "w", encoding="utf-8")
    for fid, rating in best.items():
        ft = db.fairytales.find_one({"_id": fid})
        if not ft:
            print(f"  [skip] 동화 문서 없음: {fid}")
            continue
        story = extract_story(ft.get("content"))
        if len(story) < 50:
            print(f"  [skip] 본문이 너무 짧음(미발행 추정): {fid}")
            continue
        mood = (ft.get("mood") or "").strip() or "따뜻한"
        child = db.children.find_one({"_id": ft.get("child_id")})
        age_band = age_band_from_birth_year(child.get("birth_year") if child else None)
        style = "짧은 구어체 영유아 동화 (사용자 평점 4점 이상 실물)"
        condition_key = f"대상 연령 {age_band} / 분위기 {mood} / {style}"
        ex_id = f"rated_{fid}"

        col.upsert(
            ids=[ex_id],
            documents=[condition_key],
            metadatas=[{"story": story, "age_band": age_band, "mood": mood,
                        "style": style, "source": "rated", "rating": int(rating)}],
        )
        row = {"id": ex_id, "fairy_tale_id": str(fid), "rating": int(rating),
               "age_band": age_band, "mood": mood, "condition_key": condition_key,
               "story": story}
        rows.append(row)
        out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  ok {ex_id} (평점 {rating} / 분위기 '{mood}' / {age_band})")
    out_f.close()

    print(f"\n[done] 승격 {len(rows)}편 → '{COLLECTION}' (총 {col.count()}개), 기록: {OUT}")


if __name__ == "__main__":
    main()
