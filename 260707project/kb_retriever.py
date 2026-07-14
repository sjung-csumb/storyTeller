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
        # Upstage 임베딩은 문서용(passage)과 질의용(query) 모델이 분리되어 있다.
        # 색인(문서)은 passage, 검색(질의)은 query 모델을 써야 검색 정확도가 올라간다.
        # (scripts/eval_rag.py A/B 평가로 검증: Hit@1 0.81 → 0.87)
        self.doc_embedding_fn = UpstageEmbeddingFunction(
            self.openai_client, model_name="solar-embedding-1-large-passage"
        )
        self.query_embedding_fn = UpstageEmbeddingFunction(
            self.openai_client, model_name="solar-embedding-1-large-query"
        )
        # 하위 호환: 문서 추가(build_example_db 등) 시 passage 모델을 기본으로 사용
        self.embedding_fn = self.doc_embedding_fn

        try:
            self.collection = self.chroma_client.get_collection(
                name="childcare_guide",
                embedding_function=self.doc_embedding_fn
            )
            print(f"[SUCCESS] Expert Guide DB Connected. (Total Docs: {self.collection.count()})")
        except Exception as e:
            print(f"[ERROR] Guide DB Connection Failed: {e}. Please run build script first.")
            
        try:
            self.examples_collection = self.chroma_client.get_or_create_collection(
                name="fairytale_examples",
                embedding_function=self.doc_embedding_fn
            )
            print(f"[SUCCESS] Fairytale Examples DB Connected. (Total Docs: {self.examples_collection.count()})")
        except Exception as e:
            print(f"[ERROR] Examples DB Connection Failed: {e}")

    def retrieve_few_shot(self, query: str, top_k: int = 1) -> list:
        """
        주어진 쿼리와 가장 유사한 전문가 지침 텍스트 반환 (Chroma DB 활용)
        """
        try:
            # 질의는 query 모델로 임베딩하여 검색 (문서는 passage 모델로 색인됨)
            query_embedding = self.query_embedding_fn([query])[0]
            results = self.collection.query(
                query_embeddings=[query_embedding],
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
        입력자의 조건(대상연령대/분위기)과 가장 잘 맞는 모범 동화 '본문'을 반환합니다.

        예시는 '조건 요약 키'(condition_key)로 색인되어 있고 본문(story)은 메타데이터에
        저장되어 있으므로, 검색은 조건 vs 조건으로 대칭 매칭하고 반환은 본문으로 한다.
        (색인 구성은 scripts/build_example_index.py 참고)
        """
        try:
            # 질의는 query 모델로 임베딩하여 검색 (문서는 passage 모델로 색인됨)
            query_embedding = self.query_embedding_fn([query])[0]
            results = self.examples_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            examples = []
            metadatas = results.get('metadatas') or [[]]
            documents = results.get('documents') or [[]]
            for idx in range(len(documents[0])):
                distance = results['distances'][0][idx] if results.get('distances') else 0
                print(f"  [Example Match] Distance: {distance:.3f}")
                meta = metadatas[0][idx] if metadatas and metadatas[0] else None
                # 메타데이터에 본문(story)이 있으면 그것을, 없으면(구버전 색인) 문서를 사용
                if meta and meta.get("story"):
                    examples.append(meta["story"])
                else:
                    examples.append(documents[0][idx])
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
