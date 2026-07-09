from kb_retriever import get_retriever

if __name__ == "__main__":
    print("Initializing Chroma DB Retriever...")
    retriever = get_retriever()
    
    print("\nTesting Query: '빨간 반팔티를 잃어버린 4살 소년 철수'")
    results = retriever.retrieve_few_shot("빨간 반팔티를 잃어버린 4살 소년 철수", top_k=1)
    
    if results:
        print("\n[RAG Retrieved Story]")
        print(results[0][:200] + "...")
    else:
        print("\nNo results found.")
