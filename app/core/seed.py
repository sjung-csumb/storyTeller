# Step 6.3: 초기 데이터 적재 로직 구현 (Data Seeding)
# Recap:
# Vector DB(ChromaDBRepository)와 데이터 모델(MedicalQA)이 준비되었습니다.
# 하지만 아직 DB는 텅 비어 있습니다.
# 서버가 켜질 때 자동으로 의료 데이터를 다운로드하고 DB에 적재하는 Seed Manager를 구현합니다.
# 특히 대용량 데이터를 다룰 때 메모리를 효율적으로 쓰고, 사용자에게 "데이터 준비 중..."이라는 진행
# 상황을 알려줄 수 있도록 설계합니다.

# 1. 시딩 매니저 구현 (app/core/seed.py)
# 크게 세 가지 역할을 수행합니다.
# ● 데이터 다운로드: 구글 드라이브 등에서 원본 데이터(Zip)를 받아옵니다.
# ● 데이터 정제: 한글 파일명 깨짐 현상을 해결하고, JSON을 읽어 MedicalQA 객체로 변환합니다.
# ● DB 적재: 중복을 피해 DB에 벡터 데이터를 밀어 넣습니다
# 1.1. 클래스 초기화 및 상태 관리
# 먼저 경로를 설정하고, 현재 작업 진행률을 파일(seed_status.json)로 관리하는 기본 구조를 잡습니다.
# 이는 프론트엔드나 API가 현재 서버의 준비 상태를 조회할 때 사용됩니다.

import os
import json
import logging
import zipfile
import unicodedata
import gdown
from pathlib import Path
from typing import Iterator, Dict, Any, List
from app.models.entities.medical_qa import MedicalQA
from app.service.vector_service import VectorService
from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.embedding_service import EmbeddingService
logger = logging.getLogger("seed")
class SeedManager:
    """의료 데이터 다운로드 및 벡터 DB 시딩을 담당하는 매니저 클래스"""
    def __init__(self):
        self.seed_status_file = Path("logs/seed_status.json")
        self.resource_dir = Path("resources")
        self.data_dir = self.resource_dir / "의료데이터"
        self.zip_path = self.resource_dir / "의료데이터.zip"
        self.seed_url = os.getenv("SEED_URL")
        # 서비스 초기화 (VectorService + ChromaDB + OpenAI Embedding)
        self.vector_service = VectorService(ChromaDBRepository(), EmbeddingService())
    def get_status(self) -> Dict[str, Any]:
        """현재 시딩 상태를 반환합니다 (UI 표시용)."""
        if not self.seed_status_file.exists():
            return {"status": "not_started", "current": 0, "total": 0, "message":"Ready"}
        try:
            with open(self.seed_status_file, "r") as f:
                return json.load(f)
        except Exception as e:
            return {"status": "error", "message": str(e)}
        
    def _update_status(self, status: str, current: int = 0, total: int = 0, message: str = ""):
        """상태 파일 업데이트 (내부용)"""
        try:
            with open(self.seed_status_file, "w") as f:
                json.dump({
                    "status": status,
                    "current": current,
                    "total": total,
                    "message": message
                }, f)
        except Exception as e:
            logger.error(f"Failed to update status: {e}")

    #1.2. 데이터 다운로드 및 한글 파일명 처리
    def _download_and_extract(self):
        """데이터 다운로드 및 압축 해제"""
        if not self.resource_dir.exists():
            self.resource_dir.mkdir(parents=True)
        
        # 1. 다운로드 (gdown 사용)
        if not self.zip_path.exists():
            if not self.seed_url:
                raise ValueError("SEED_URL environment variable is not set.")
            logger.info("Downloading data...")
            gdown.download(self.seed_url, str(self.zip_path), quiet=False)
        
        # 2. 압축 해제 및 인코딩 보정
        logger.info(f"Extracting {self.zip_path}...")
        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                # 한글 파일명 인코딩 보정 (cp437 -> cp949 -> NFC 정규화)
                try:
                        filename = file_info.filename.encode('cp437').decode('cp949')
                except:
                    filename = file_info.filename
                
                filename = unicodedata.normalize('NFC', filename)

                # 경로 설정
                if filename.startswith('의료데이터/'):
                    target_path = self.resource_dir / filename
                else:
                    target_path = self.resource_dir / filename
                
                if file_info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zip_ref.open(file_info) as source, open(target_path,"wb") as target:
                        target.write(source.read())
        #폴더명 후처리 (압축 해제 후 경로가 맞지 않을 경우 대비)
        extracted_dirs = [d for d in self.resource_dir.iterdir() if d.is_dir() and d.name != "__MACOSX"]
        if not self.data_dir.exists() and extracted_dirs:
            candidate = extracted_dirs[0]
            logger.info(f"Renaming {candidate.name} to {self.data_dir.name}")
            candidate.rename(self.data_dir)
    
    #1.3. 메모리 효율적인 데이터 제너레이터
    # 수천 개의 파일을 한 번에 리스트에 담으면 메모리 부족이 발생할 수 있습니다.
    # yield를 사용하여 필요할 때 하나씩 읽어오는 Generator 패턴을 적용합니다.
    def _load_documents_generator(self) -> Iterator[MedicalQA]:
        """JSON 파일을 읽어 문서를 하나씩 반환하는 제너레이터 (메모리 절약)"""
        if not self.data_dir.exists():
            self._download_and_extract()
        logger.info(f"Loading documents from {self.data_dir}")
        count = 0
        for file_path in self.data_dir.rglob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)

                    # 검색에 쓰일 문서 포맷팅 (질문 + 답변)
                    document = f"Q: {data.get('question', '')}\nA:{data.get('answer', '')}"

                    # 메타데이터 구성
                    extra_info = f"Domain: {data.get('domain', 'N/A')}, Type: {data.get('q_type', 'N/A')}"
                    
                    yield MedicalQA(
                        id=f"medical_{data.get('qa_id', file_path.stem)}",
                        document=document,
                        metadata={"extra_info": extra_info}
                    )
                    count += 1
            except Exception as e:
                    logger.error(f"Error parsing {file_path}: {e}")
        
        logger.info(f"Total documents loaded from generator: {count}")

    # 1.4. 시딩 실행 메인 로직
    # 실제 적재를 수행합니다.
    # ● 중복 방지: 이미 DB에 데이터가 충분하다면 작업을 건너뜁니다.
    # ● 배치 처리: 데이터를 100개씩 묶어서(batch) DB에 전송하여 네트워크 부하를 줄입니다.

    def run(self):
        """시딩 프로세스 메인 실행 함수"""
        try:
            from app.core.db import ChromaDBConfig
            config = ChromaDBConfig()
            logger.info(f"Starting seeding process. Mode: {config.mode}")

            # 1. 파일 시스템 확인
            self._update_status("in_progress", 0, 0, "Checking file integrity...")
            documents = list(self._load_documents_generator()) # 전체 개수 파악을 위해 1회 순회
            total_docs = len(documents)
            if total_docs == 0:
                self._update_status("completed", 0, 0, "No data files found.")
                return
            
            # 2. DB 상태 확인 (이미 적재되었는지 체크)
            info = self.vector_service.get_collection_info()
            current_db_count = info["count"]
            
            if current_db_count >= total_docs:
                logger.info(f"Skipping seeding (DB: {current_db_count} >= Files: {total_docs})")
                self._update_status("completed", current_db_count, total_docs, "Already seeded.")
                return
            
            # 3. 배치 단위 적재 시작
            batch_size = 100
            self._update_status("in_progress", current_db_count, total_docs,"Inserting vectors...")
            
            for i in range(0, total_docs, batch_size):
                batch: List[MedicalQA] = documents[i: i + batch_size]

                self.vector_service.add_documents(
                    documents=[d.document for d in batch],
                    metadatas=[d.metadata for d in batch],
                    ids=[d.id for d in batch]
                )
                current = min(i + len(batch), total_docs)
                self._update_status("in_progress", current, total_docs,
                                    f"Seeding... {int(current / total_docs * 100)}%")
                logger.info(f"Seeded batch {current}/{total_docs}")
            self._update_status("completed", total_docs, total_docs, "Seeding completed.")
        
        except Exception as e:
            logger.exception("Seeding failed")
            self._update_status("error", 0, 0, str(e))
            raise e



# 1.5. 클래스 초기화 및 상태 관리
# 마지막으로, 싱글톤 인스턴스를 생성하고 외부(main.py 등)에서 쉽게 호출할 수 있도록 래퍼 함수를
# 만듭니다.

# 싱글톤 인스턴스
seed_manager = SeedManager()

def get_seed_status():
    return seed_manager.get_status()

def seed_data_if_empty():
    seed_manager.run()

