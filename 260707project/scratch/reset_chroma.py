import chromadb
from kb_retriever import get_retriever

def reset_and_rebuild():
    client = chromadb.PersistentClient(path="./data/chroma_db")
    try:
        client.delete_collection("fairytale_collection")
        print("Deleted existing fairytale_collection.")
    except Exception as e:
        print(f"Collection not found or couldn't delete: {e}")
        
    print("Rebuilding Chroma DB with new data...")
    # get_retriever()를 호출하면 알아서 490개 데이터를 읽어와서 새 컬렉션을 만들고 임베딩함
    # 단, 싱글톤 객체를 새로 만들어야 하므로 모듈 리로드가 필요할 수 있지만, 
    # 독립된 스크립트 실행이므로 그냥 호출해도 됩니다.
    get_retriever(data_paths=["data/formatted_train.jsonl"])
    print("Done!")

if __name__ == "__main__":
    reset_and_rebuild()
