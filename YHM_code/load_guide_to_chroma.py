import json
import os
import chromadb

OUTPUT_DIR = "./chroma_db"
INPUT_JSON = os.path.join(OUTPUT_DIR, "guide_collection.json")
PERSIST_DIR = os.path.join(OUTPUT_DIR, "guide_chroma_db")

print("📖 1. guide_collection.json 읽는 중...")
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

collection_name = data["collection_name"]
ids = data["ids"]
embeddings = data["embeddings"]
documents = data["documents"]
metadatas = data["metadatas"]

print(f"📚 로드 대상: {collection_name} (총 {len(ids)}개 항목)")

client = chromadb.PersistentClient(path=PERSIST_DIR)

existing = [c.name for c in client.list_collections()]
if collection_name in existing:
    print(f"⚠️ 기존 '{collection_name}' 컬렉션 발견 → 삭제 후 재생성")
    client.delete_collection(collection_name)

collection = client.create_collection(name=collection_name)

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