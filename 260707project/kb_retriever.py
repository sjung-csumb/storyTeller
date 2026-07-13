import json
import os
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from openai import OpenAI
import numpy as np
from dotenv import load_dotenv

load_dotenv()

class UpstageEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    ChromaDB를 위한 Upstage(Solar) 임베딩 래퍼 클래스.
    OpenAI 클라이언트 포맷을 사용하여 API를 호출합니다.
    """
    def __init__(self, client, model_name: str = "solar-embedding-1-large-query"):
        self.client = client
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        if not all(isinstance(item, str) for item in input):
            raise ValueError("Solar embedding only supports text documents")
            
        batch_process_result = self.client.embeddings.create(
            model=self.model_name, 
            input=input
        ).data
        
        passage_embedding_list = [i.embedding for i in batch_process_result]
        return np.array(passage_embedding_list, dtype=np.float32).tolist()


class FairyTaleRetriever:
    def __init__(self, db_path: str = "data/guide_chroma_db"):
        self.db_path = db_path
        
        # OpenAI 클라이언트를 Upstage 엔드포인트로 설정
        api_key = os.environ.get("UPSTAGE_API_KEY")
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY is missing!")
            
        self.openai_client = OpenAI(
            api_key=api_key,
            base_url="https://api.upstage.ai/v1/solar"
        )
        
        # Chroma DB 클라이언트 및 컬렉션 세팅
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.embedding_fn = UpstageEmbeddingFunction(self.openai_client)
        
        try:
            self.collection = self.chroma_client.get_collection(
                name="childcare_guide", 
                embedding_function=self.embedding_fn
            )
            print(f"[SUCCESS] Expert Guide DB Connected. (Total Docs: {self.collection.count()})")
        except Exception as e:
            print(f"[ERROR] Guide DB Connection Failed: {e}. Please run build script first.")
            
        try:
            self.examples_collection = self.chroma_client.get_or_create_collection(
                name="fairytale_examples",
                embedding_function=self.embedding_fn
            )
            print(f"[SUCCESS] Fairytale Examples DB Connected. (Total Docs: {self.examples_collection.count()})")
        except Exception as e:
            print(f"[ERROR] Examples DB Connection Failed: {e}")

    def retrieve_few_shot(self, query: str, top_k: int = 1) -> list:
        """
        주어진 쿼리와 가장 유사한 전문가 지침 텍스트 반환 (Chroma DB 활용)
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            # 결과에서 'documents'(전문가 지침 텍스트) 추출
            guides = []
            if results['documents'] and len(results['documents'][0]) > 0:
                for idx, doc in enumerate(results['documents'][0]):
                    distance = results['distances'][0][idx] if 'distances' in results and results['distances'] else 0
                    print(f"  [Chroma Match] Distance: {distance:.3f}")
                    guides.append(doc)
                    
            return guides
        except Exception as e:
            print(f"Error during Chroma semantic retrieval: {e}")
            return []

    def retrieve_example(self, query: str, top_k: int = 1) -> list:
        """
        주어진 쿼리(아이 성향/상황)와 가장 유사한 모범 동화 예시를 반환합니다.
        """
        try:
            results = self.examples_collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            examples = []
            if results['documents'] and len(results['documents'][0]) > 0:
                for idx, doc in enumerate(results['documents'][0]):
                    distance = results['distances'][0][idx] if 'distances' in results and results['distances'] else 0
                    print(f"  [Example Match] Distance: {distance:.3f}")
                    examples.append(doc)
            return examples
        except Exception as e:
            print(f"Error during Example semantic retrieval: {e}")
            return []
            
    def build_example_db(self, jsonl_path: str):
        """
        formatted_human.jsonl 파일을 읽어서 examples_collection에 임베딩합니다.
        """
        if not os.path.exists(jsonl_path):
            print(f"[ERROR] File not found: {jsonl_path}")
            return
            
        print("[INFO] Building Fairytale Examples DB...")
        documents = []
        ids = []
        
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                try:
                    data = json.loads(line)
                    # assistant의 응답(완성된 동화 JSON) 추출
                    messages = data.get("messages", [])
                    if len(messages) >= 2 and messages[1]["role"] == "assistant":
                        fairytale_json_str = messages[1]["content"]
                        documents.append(fairytale_json_str)
                        ids.append(f"example_{i}")
                except Exception as e:
                    print(f"[WARN] Error parsing line {i}: {e}")
                    continue
                    
        if documents:
            # 배치 단위로 추가 (임베딩 API 제한 고려)
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                self.examples_collection.upsert(
                    documents=batch_docs,
                    ids=batch_ids
                )
                print(f"[INFO] Upserted batch {i//batch_size + 1}")
            print(f"[SUCCESS] Added {len(documents)} examples to ChromaDB.")
        else:
            print("[WARN] No valid examples found in file.")

# Singleton instance
retriever = None

def get_retriever():
    global retriever
    if retriever is None:
        retriever = FairyTaleRetriever()
    return retriever
