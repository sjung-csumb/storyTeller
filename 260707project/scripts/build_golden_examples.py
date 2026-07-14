"""
골든 예시 생성 & 예시 인덱스 교체
=================================

기존 fairytale_examples 코퍼스(289편)는 대상연령 5~7세·7~8페이지로 SMILE(영유아·4페이지)와
맞지 않는다. 그래서 SMILE 자신의 draft 파이프라인으로 **영유아 4페이지 '골든 예시' 8편**을
분위기 아키타입 4종 × 2편으로 생성하고, 예시 컬렉션을 이 골든 예시로 **교체**한다.

  - 색인(임베딩) : 조건 요약 키(condition_key)  → 분위기 매칭
  - 메타데이터    : story(4페이지 본문), age_band, mood, style

산출물: data/golden_examples.jsonl  (재현/기록용)
DB    : data/guide_chroma_db 의 fairytale_examples 컬렉션을 골든 8편으로 교체

실행: uv run python scripts/build_golden_examples.py
"""
import os
import sys
import json
from types import SimpleNamespace

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from kb_retriever import UpstageEmbeddingFunction
from llm import generate_draft_text, split_story_pages

load_dotenv()

DB_PATH = "data/guide_chroma_db"
OUT = "data/golden_examples.jsonl"
COLLECTION = "fairytale_examples"
PASSAGE_MODEL = "solar-embedding-1-large-passage"

APPEARANCE = "동그란 얼굴에 짧은 머리, 볼이 통통하고 표정이 밝은 아이"

# 분위기 아키타입 4종 × 2편 = 8. 문제상황·배경을 다양화해 플롯 편중을 줄인다.
SPECS = [
    # (mood, personality, place, problem_situation)
    ("따뜻하고 잔잔한", "수줍음", "포근한 집 거실", "동생에게 장난감을 양보하지 않아요"),
    ("따뜻하고 잔잔한", "예민함", "아늑한 침실", "혼자 자는 걸 무서워해요"),
    ("밝고 경쾌한", "활발함", "알록달록한 놀이방", "가지고 논 장난감을 정리하지 않아요"),
    ("밝고 경쾌한", "까다로움", "집 식탁", "채소를 안 먹고 편식이 심해요"),
    ("모험적이고 신나는", "에너지가 넘침", "놀이터", "화가 나면 친구를 밀쳐요"),
    ("모험적이고 신나는", "성급함", "놀이공원", "차례를 기다리지 않고 새치기해요"),
    ("차분하고 교훈적인", "상상력이 풍부함", "어린이집", "잘못을 하고 거짓말을 해요"),
    ("차분하고 교훈적인", "고집이 셈", "마트", "원하는 걸 안 사주면 떼를 써요"),
]


def main():
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("[ERROR] UPSTAGE_API_KEY 필요")
        return

    rows = []
    out_f = open(OUT, "w", encoding="utf-8")
    for i, (mood, personality, place, problem) in enumerate(SPECS):
        child = SimpleNamespace(name="아이", birth_year=2022, gender="무관")  # 만 4세
        print(f"\n[{i+1}/8] 생성: 분위기='{mood}', 문제='{problem}'")
        try:
            draft_text, _ = generate_draft_text(
                child=child, appearance=APPEARANCE, personality=personality,
                place=place, time_period="현대", mood=mood,
                problem_situation=problem, language="ko",
            )
        except Exception as e:
            print(f"  [warn] 생성 실패: {e}")
            continue

        pages = split_story_pages(draft_text)
        story = "\n".join(pages) if pages else draft_text.strip()
        condition_key = f"대상 연령 3~4세 / 분위기 {mood} / 짧은 구어체 4페이지 영유아 동화"
        row = {
            "id": f"golden_{i}",
            "age_band": "3~4세",
            "mood": mood,
            "style": "짧은 구어체 4페이지 영유아 동화",
            "condition_key": condition_key,
            "story": story,
            "_meta": {"problem": problem, "place": place, "personality": personality},
        }
        rows.append(row)
        out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        out_f.flush()
        print(f"  ok (본문 {len(story)}자, 페이지 {len(pages)}개)")
    out_f.close()
    print(f"\n[saved] {OUT} ({len(rows)}편)")

    if not rows:
        print("[ERROR] 생성된 골든 예시가 없어 인덱스를 교체하지 않습니다.")
        return

    # --- 예시 컬렉션 교체 ---
    client = OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],
                    base_url="https://api.upstage.ai/v1/solar")
    passage_ef = UpstageEmbeddingFunction(client, model_name=PASSAGE_MODEL)
    chroma = chromadb.PersistentClient(path=DB_PATH)
    if COLLECTION in {c.name for c in chroma.list_collections()}:
        chroma.delete_collection(COLLECTION)
        print(f"[reset] 기존 '{COLLECTION}' 삭제 (289편 코퍼스 제거)")
    col = chroma.create_collection(COLLECTION, embedding_function=passage_ef)
    col.add(
        documents=[r["condition_key"] for r in rows],
        ids=[r["id"] for r in rows],
        metadatas=[{"story": r["story"], "age_band": r["age_band"],
                    "mood": r["mood"], "style": r["style"]} for r in rows],
    )
    print(f"[done] '{COLLECTION}' 골든 예시로 교체 완료 (count={col.count()})")


if __name__ == "__main__":
    main()
