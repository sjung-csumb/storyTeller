import os
import shutil
import pdfplumber
import chromadb
from chromadb import Documents
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kb_retriever import UpstageEmbeddingFunction
from openai import OpenAI

load_dotenv()

PDF_PATH = "data/[수탁보고 2013] 영유아 문제행동지도를 위한 어린이집 보육교사 지침서.pdf"
DB_PATH = "data/guide_chroma_db"
COLLECTION_NAME = "childcare_guide"

def main():
    print(f"1. PDF 파싱 시작: {PDF_PATH}")
    full_text = ""
    try:
        with pdfplumber.open(PDF_PATH) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    # 불필요한 줄바꿈 제거 및 정리
                    clean_text = text.replace('\n', ' ').strip()
                    full_text += clean_text + " "
                if (i+1) % 20 == 0:
                    print(f"  - Parsing... ({i+1}/{total_pages} pages)")
    except Exception as e:
        print(f"PDF 파싱 실패: {e}")
        return

    print(f"\n2. 텍스트 청킹 (Chunking) 시작...")
    # 전문가 문서이므로 너무 짧게 자르면 문맥이 끊김
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_text(full_text)
    print(f"  - 총 {len(chunks)}개의 청크(문단)로 분리되었습니다.")

    print(f"\n3. 기존 Chroma DB 초기화...")
    if os.path.exists(DB_PATH):
        try:
            shutil.rmtree(DB_PATH)
            print("  - 기존 DB 폴더 삭제 완료.")
        except Exception as e:
            print(f"  - 폴더 삭제 실패 (무시하고 덮어쓰기 시도): {e}")

    print(f"\n4. 임베딩 및 Chroma DB 적재 시작...")
    upstage_client = OpenAI(
        api_key=os.environ.get("UPSTAGE_API_KEY"),
        base_url="https://api.upstage.ai/v1/solar"
    )
    embedding_func = UpstageEmbeddingFunction(client=upstage_client)
    
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_func
    )

    # API Rate Limit 방지를 위해 100개씩 쪼개서 넣기
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i+batch_size]
        batch_ids = [f"guide_doc_{j}" for j in range(i, i+len(batch_chunks))]
        
        # 메타데이터 (출처 표기)
        batch_metadatas = [{"source": "보건복지부 지침서 2013", "type": "expert_guide"} for _ in batch_chunks]
        
        collection.add(
            documents=batch_chunks,
            ids=batch_ids,
            metadatas=batch_metadatas
        )
        print(f"  - 적재 중... ({min(i+len(batch_chunks), len(chunks))}/{len(chunks)})")
        
    print("\n[SUCCESS] 모든 데이터가 성공적으로 새로운 Chroma DB에 구축되었습니다!")

if __name__ == "__main__":
    main()
