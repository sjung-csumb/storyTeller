"""
동화 예시 인덱스 재구축 (조건요약키 기반)
=========================================

data/example_labels.jsonl (label_examples.py 산출물)을 읽어 fairytale_examples
컬렉션을 재구축한다. 기존처럼 '완성된 이야기 JSON'을 임베딩하지 않고, 각 예시의
'조건 요약 키(condition_key)'를 passage 모델로 색인한다.
  - 색인(임베딩 대상) : condition_key  (예: "대상 연령 5~7세 / 분위기 따뜻한 / ...")
  - 메타데이터        : story(한국어 본문), age_band, mood, style

이렇게 하면 입력자의 '나이·분위기' 질의와 예시의 '조건 키'가 대칭 매칭되고,
few-shot 으로는 메타데이터의 story(본문)만 전달한다.

실행: uv run python scripts/build_example_index.py
"""
import os
import sys
import json

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from kb_retriever import UpstageEmbeddingFunction

load_dotenv()

DB_PATH = "data/guide_chroma_db"
LABELS = "data/example_labels.jsonl"
COLLECTION = "fairytale_examples"
PASSAGE_MODEL = "solar-embedding-1-large-passage"
BATCH = 100


def main():
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("[ERROR] UPSTAGE_API_KEY 필요")
        return
    if not os.path.exists(LABELS):
        print(f"[ERROR] {LABELS} 없음. 먼저 scripts/label_examples.py 실행")
        return

    rows = [json.loads(l) for l in open(LABELS, encoding="utf-8") if l.strip()]
    print(f"[load] 라벨 {len(rows)}개")

    client = OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],
                    base_url="https://api.upstage.ai/v1/solar")
    passage_ef = UpstageEmbeddingFunction(client, model_name=PASSAGE_MODEL)
    chroma = chromadb.PersistentClient(path=DB_PATH)

    if COLLECTION in {c.name for c in chroma.list_collections()}:
        chroma.delete_collection(COLLECTION)
        print(f"[reset] 기존 '{COLLECTION}' 삭제")
    col = chroma.create_collection(COLLECTION, embedding_function=passage_ef)

    docs = [r["condition_key"] for r in rows]           # 임베딩 대상
    ids = [r["id"] for r in rows]
    metas = [{
        "story": r["story"],
        "age_band": r.get("age_band", ""),
        "mood": r.get("mood", ""),
        "style": r.get("style", ""),
    } for r in rows]

    for i in range(0, len(docs), BATCH):
        col.add(documents=docs[i:i + BATCH], ids=ids[i:i + BATCH],
                metadatas=metas[i:i + BATCH])
        print(f"  - indexed {min(i + BATCH, len(docs))}/{len(docs)}")

    print(f"[done] '{COLLECTION}' 재구축 완료 (count={col.count()})")

    # 연령대 분포 요약 (age 매칭이 유효한지 참고용)
    from collections import Counter
    dist = Counter(r.get("age_band", "?") for r in rows)
    print("[info] 대상연령대 분포:", dict(dist))


if __name__ == "__main__":
    main()
