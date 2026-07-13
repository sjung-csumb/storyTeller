import os
import chromadb
from dotenv import load_dotenv

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kb_retriever import UpstageEmbeddingFunction
from openai import OpenAI

load_dotenv()

DB_PATH = "data/guide_chroma_db"
COLLECTION_NAME = "childcare_guide"

def main():
    print("1. Upstage Embedding Function 초기화...")
    upstage_client = OpenAI(
        api_key=os.environ.get("UPSTAGE_API_KEY"),
        base_url="https://api.upstage.ai/v1/solar"
    )
    embedding_func = UpstageEmbeddingFunction(client=upstage_client)
    
    print("2. Chroma DB 연결...")
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    try:
        collection = chroma_client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_func
        )
    except Exception as e:
        print(f"[ERROR] 컬렉션을 찾을 수 없습니다: {e}")
        return
        
    print(f"  - 현재 적재된 문서 수: {collection.count()} 개")
    
    print("\n3. 검색 테스트 진행...")
    query = "아이가 화가 나면 친구를 때리거나 물건을 던집니다. 어떻게 훈육해야 하나요?"
    print(f"  - 검색 쿼리: '{query}'")
    
    results = collection.query(
        query_texts=[query],
        n_results=2
    )
    
    print("\n================ [검색 결과] ================")
    for i, doc in enumerate(results['documents'][0]):
        distance = results['distances'][0][i]
        print(f"\n[Rank {i+1}] (유사도 거리: {distance:.3f})")
        safe_doc = doc.encode('cp949', errors='replace').decode('cp949')
        print(f"{safe_doc}")
        print("-" * 50)

if __name__ == "__main__":
    main()
