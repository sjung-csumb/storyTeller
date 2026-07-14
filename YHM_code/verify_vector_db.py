import json

with open("./chroma_db/local_vector_index.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("컬렉션 이름:", data["collection_name"])
print("문서(청크) 개수:", len(data["documents"]))
print("임베딩 개수:", len(data["embeddings"]))
print("ID 개수:", len(data["ids"]))
print("첫 임베딩 벡터 차원:", len(data["embeddings"][0]))  # solar-embedding-1-large는 4096차원이어야 정상
print("샘플 문서 일부:", data["documents"][0][:100])