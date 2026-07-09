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
    def __init__(self, data_paths: list = None, db_path: str = "./data/chroma_db"):
        if data_paths is None:
            data_paths = ["data/formatted_train.jsonl", "data/formatted_val.jsonl"]
        self.data_paths = data_paths
        
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
        
        self.collection = self.chroma_client.get_or_create_collection(
            name="fairytales", 
            embedding_function=self.embedding_fn
        )
        
        self._load_data()

    def _load_data(self):
        """데이터를 파싱하고 Chroma DB에 적재합니다."""
        # 1. 이미 DB에 데이터가 있는지 확인 (Persistence 장점)
        existing_count = self.collection.count()
        if existing_count > 0:
            print(f"[SUCCESS] KB Retriever: Chroma DB loaded with {existing_count} existing records.")
            return

        # 2. 비어있다면 소스 파일 파싱 및 임베딩 진행
        print("Chroma DB is empty. Parsing source files and generating embeddings... This may take a moment.")
        docs = []
        metadatas = []
        ids = []
        
        doc_id = 0
        for path in self.data_paths:
            if not os.path.exists(path):
                print(f"Warning: Data file {path} not found. Skipping.")
                continue

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            data = json.loads(line.strip())
                            messages = data.get("messages", [])
                            
                            user_query = ""
                            assistant_response = ""
                            for msg in messages:
                                if msg["role"] == "user":
                                    user_query = msg["content"]
                                if msg["role"] == "assistant":
                                    assistant_response = msg["content"]
                            
                            if user_query and assistant_response:
                                docs.append(user_query)
                                # 메타데이터에는 실제 동화 JSON 텍스트를 통째로 보관합니다.
                                metadatas.append({"tale": assistant_response})
                                ids.append(f"doc_{doc_id}")
                                doc_id += 1
                                
                        except Exception:
                            pass
            except Exception as e:
                print(f"Error loading KB data from {path}: {e}")

        if not docs:
            print("Warning: No valid documents found to add to Chroma DB.")
            return

        # 3. DB에 일괄 추가 (UpstageEmbeddingFunction이 자동으로 호출됨)
        # ChromaDB API Limits: 일반적으로 배치를 나눠서 넣는 것이 안전하지만, 300~400개는 한 번에 처리 가능합니다.
        batch_size = 100
        for i in range(0, len(docs), batch_size):
            end_idx = i + batch_size
            print(f"Adding batch {i} to {end_idx}...")
            self.collection.add(
                documents=docs[i:end_idx],
                metadatas=metadatas[i:end_idx],
                ids=ids[i:end_idx]
            )
        
        print(f"[SUCCESS] KB Retriever: Saved {len(docs)} embeddings to Chroma DB.")

    def retrieve_few_shot(self, query: str, top_k: int = 1) -> list:
        """
        주어진 쿼리와 가장 유사한 과거 동화 데이터 반환 (Chroma DB 활용)
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            # 결과에서 메타데이터('tale') 추출
            tales = []
            if results['metadatas'] and len(results['metadatas'][0]) > 0:
                for idx, meta in enumerate(results['metadatas'][0]):
                    distance = results['distances'][0][idx] if 'distances' in results and results['distances'] else 0
                    print(f"  [Chroma Match] Distance: {distance:.3f}")
                    tales.append(meta["tale"])
                    
            return tales
        except Exception as e:
            print(f"Error during Chroma semantic retrieval: {e}")
            return []

# Singleton instance
retriever = None

def get_retriever(data_paths=["data/formatted_train.jsonl", "data/formatted_val.jsonl"]):
    global retriever
    if retriever is None:
        retriever = FairyTaleRetriever(data_paths=data_paths)
    return retriever
