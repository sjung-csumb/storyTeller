import json
import urllib.request
import chromadb
import os
from dotenv import load_dotenv

load_dotenv()
OS_API_KEY = os.environ["UPSTAGE_API_KEY"]
PERSIST_DIR = "./chroma_db/guide_chroma_db"

def embed_query(text):
    url = "https://api.upstage.ai/v1/solar/embeddings"
    headers = {"Authorization": f"Bearer {OS_API_KEY}", "Content-Type": "application/json"}
    body = json.dumps({
        "model": "solar-embedding-1-large-query",
        "input": [text]
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as res:
        res_data = json.loads(res.read().decode("utf-8"))
        return res_data["data"][0]["embedding"]

client = chromadb.PersistentClient(path=PERSIST_DIR)
collection = client.get_collection(name="childcare_guide")

test_query = "영유아 문제행동이 나타날 때 교사의 대응 방법"  # 원하시는 질문으로 바꿔보세요
query_vector = embed_query(test_query)

results = collection.query(
    query_embeddings=[query_vector],
    n_results=3
)

print(f"🔍 질문: {test_query}\n")
for i, (doc, dist) in enumerate(zip(results["documents"][0], results["distances"][0])):
    print(f"[{i+1}] 유사도 거리: {dist:.4f}")
    print(doc[:200])
    print("---")