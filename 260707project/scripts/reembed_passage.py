"""
가이드/예시 DB를 passage 임베딩으로 재색인 (in-place)
=====================================================

기존 data/guide_chroma_db 의 두 컬렉션(childcare_guide, fairytale_examples)은
`solar-embedding-1-large-query` 모델로 색인되어 있다. 이를 문서용 모델인
`solar-embedding-1-large-passage` 로 다시 임베딩한다. (질의는 kb_retriever 가
query 모델로 임베딩하여 검색 → passage/query 분리)

PDF 재파싱 없이, DB에 이미 저장된 청크 텍스트를 그대로 재사용하므로 청크 구성은
동일하게 유지되고 임베딩 벡터만 교체된다.

효과 검증: scripts/eval_rag.py (Hit@1 0.81 → 0.87, MRR 0.882 → 0.927)

실행: uv run python scripts/reembed_passage.py
"""
import os
import sys

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from kb_retriever import UpstageEmbeddingFunction

load_dotenv()

DB_PATH = "data/guide_chroma_db"
PASSAGE_MODEL = "solar-embedding-1-large-passage"
COLLECTIONS = ["childcare_guide", "fairytale_examples"]
BATCH = 100


def valid_metadatas(metas):
    """Chroma 는 None 메타데이터를 허용하지 않는다. 전부 dict 일 때만 사용."""
    if metas and all(isinstance(m, dict) and len(m) > 0 for m in metas):
        return metas
    return None


def main():
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("[ERROR] UPSTAGE_API_KEY 가 필요합니다 (.env)")
        return

    client = OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],
                    base_url="https://api.upstage.ai/v1/solar")
    passage_ef = UpstageEmbeddingFunction(client, model_name=PASSAGE_MODEL)
    chroma = chromadb.PersistentClient(path=DB_PATH)

    existing = {c.name for c in chroma.list_collections()}

    for name in COLLECTIONS:
        if name not in existing:
            print(f"[skip] '{name}' 컬렉션 없음")
            continue

        src = chroma.get_collection(name)
        data = src.get(include=["documents", "metadatas"])
        docs = data["documents"]
        ids = data["ids"]
        metas = valid_metadatas(data.get("metadatas"))
        print(f"[{name}] 기존 문서 {len(docs)}개 로드 (metadata={'유' if metas else '무'})")

        # 컬렉션 삭제 후 passage 임베딩으로 재생성
        chroma.delete_collection(name)
        col = chroma.create_collection(name=name, embedding_function=passage_ef)

        for i in range(0, len(docs), BATCH):
            kwargs = dict(documents=docs[i:i + BATCH], ids=ids[i:i + BATCH])
            if metas:
                kwargs["metadatas"] = metas[i:i + BATCH]
            col.add(**kwargs)
            print(f"  - re-embedded {min(i + BATCH, len(docs))}/{len(docs)}")

        print(f"[{name}] 재색인 완료 (count={col.count()})\n")

    print("[SUCCESS] passage 모델 재색인 완료. kb_retriever 는 query 모델로 검색합니다.")


if __name__ == "__main__":
    main()
