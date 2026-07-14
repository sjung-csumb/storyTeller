from kb_retriever import get_retriever

def main():
    print("Testing Solar Embedding Retriever Initialization...")
    # 이것이 호출될 때 캐시가 없으면 임베딩 API를 380여번 호출할 것입니다.
    # 시간이 걸릴 수 있으므로 1~2분 소요 예상
    retriever = get_retriever()
    
    print("\nTesting retrieval...")
    query = "밥을 안 먹고 젤리만 먹으려 떼쓰는 4살 남자아이"
    print(f"Query: {query}")
    
    results = retriever.retrieve_few_shot(query, top_k=1)
    
    if results:
        print("\n[SUCCESS] Found a semantic match!")
        print(f"Match content preview: {results[0][:100]}...")
    else:
        print("\n[ERROR] No matches found or an error occurred.")

if __name__ == "__main__":
    main()
