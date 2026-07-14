import json
import os
import chromadb

OUTPUT_DIR = "./chroma_db"
INPUT_JSON = os.path.join(OUTPUT_DIR, "local_vector_index.json")
PERSIST_DIR = os.path.join(OUTPUT_DIR, "tales_chroma_db")  # 실제 ChromaDB가 저장될 폴더

# ---- 1. 기존 JSON 데이터 읽기 ----
print("📖 1. local_vector_index.json 읽는 중...")
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

collection_name = data["collection_name"]
ids = data["ids"]
embeddings = data["embeddings"]
documents = data["documents"]
metadatas = data["metadatas"]

print(f"📚 로드 대상: {collection_name} (총 {len(ids)}개 항목)")

# ---- 2. ChromaDB 클라이언트 생성 (로컬 디스크에 영구 저장) ----
client = chromadb.PersistentClient(path=PERSIST_DIR)

# 기존에 같은 이름 컬렉션이 있으면 삭제 후 새로 생성 (중복 로드 방지)
existing = [c.name for c in client.list_collections()]
if collection_name in existing:
    print(f"⚠️ 기존 '{collection_name}' 컬렉션 발견 → 삭제 후 재생성")
    client.delete_collection(collection_name)

collection = client.create_collection(name=collection_name)

# ---- 3. 데이터 삽입 (Chroma는 배치 삽입 시 개수 제한이 있어 500개씩 나눠서 처리) ----
batch_size = 500
total = len(ids)

print("🧠 2. ChromaDB에 데이터 삽입 중...")
for i in range(0, total, batch_size):
    end = min(i + batch_size, total)
    collection.add(
        ids=ids[i:end],
        embeddings=embeddings[i:end],
        documents=documents[i:end],
        metadatas=metadatas[i:end],
    )
    print(f"🔄 삽입 진행률: {end}/{total}")

print(f"✅ 완료! 컬렉션 '{collection_name}'에 총 {collection.count()}개 항목 저장됨")
print(f"✨ ChromaDB 저장 위치: {PERSIST_DIR}")