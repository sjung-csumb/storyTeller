import json
import os
import re
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
OS_API_KEY = os.environ["UPSTAGE_API_KEY"]
OUTPUT_DIR = "./chroma_db"
MARKDOWN_INPUT = os.path.join(OUTPUT_DIR, "guide_markdown.md")
GUIDE_OUTPUT = os.path.join(OUTPUT_DIR, "guide_collection.json")   # 동화 컬렉션과 완전히 분리된 파일
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "guide_checkpoint.json")

# ---- 1단계: 마크다운 읽기 + 헤더 기준 청킹 ----
print("📖 1. guide_markdown.md 읽는 중...")
with open(MARKDOWN_INPUT, "r", encoding="utf-8") as f:
    markdown_text = f.read()

sections = re.split(r'(?=^#{1,3} )', markdown_text, flags=re.MULTILINE)
sections = [s.strip() for s in sections if s.strip()]

max_chars = 800
chunks_texts = []
for sec in sections:
    if len(sec) <= max_chars:
        chunks_texts.append(sec)
    else:
        for i in range(0, len(sec), max_chars):
            piece = sec[i:i + max_chars].strip()
            if piece:
                chunks_texts.append(piece)

print(f"📚 청킹 완료: 총 {len(chunks_texts)}개 청크")

# ---- 2단계: 체크포인트 확인 (중단 시 이어서 진행) ----
embeddings = []
start_idx = 0
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as cf:
        ckpt = json.load(cf)
        embeddings = ckpt["embeddings"]
        start_idx = len(embeddings)
    print(f"🔁 체크포인트 발견! {start_idx}번째부터 이어서 진행합니다.")

# ---- 3단계: Solar 임베딩 (fairy_tales 때와 동일한 재시도 로직) ----
url = "https://api.upstage.ai/v1/solar/embeddings"
headers = {"Authorization": f"Bearer {OS_API_KEY}", "Content-Type": "application/json"}
REQUEST_DELAY = 0.5
MAX_RETRIES = 5

print("🧠 2. Upstage API 연동하여 Solar 임베딩 추출 시작...")

for idx in range(start_idx, len(chunks_texts)):
    text = chunks_texts[idx]
    req_body = json.dumps({
        "model": "solar-embedding-1-large-passage",
        "input": [text]
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                embeddings.append(res_data["data"][0]["embedding"])
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 2 ** attempt
                print(f"⏳ 429 발생 (위치 {idx}, 시도 {attempt}/{MAX_RETRIES}) → {wait_time}초 대기...")
                time.sleep(wait_time)
                continue
            else:
                err_body = e.read().decode("utf-8")
                print(f"❌ 에러 발생 (위치 {idx}): {e}\n서버 응답: {err_body}")
                with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
                    json.dump({"embeddings": embeddings}, cf)
                exit()
    else:
        print(f"❌ 위치 {idx}: 재시도 {MAX_RETRIES}회 모두 실패. 스크립트를 다시 실행해 이어서 진행하세요.")
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
            json.dump({"embeddings": embeddings}, cf)
        exit()

    if (idx + 1) % 50 == 0 or (idx + 1) == len(chunks_texts):
        print(f"🔄 진행률: {idx + 1}/{len(chunks_texts)} 완료...")
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
            json.dump({"embeddings": embeddings}, cf)

    time.sleep(REQUEST_DELAY)

print(f"✅ 총 {len(embeddings)}개 청크 임베딩 완료!")

# ---- 4단계: 지침서 전용 컬렉션 저장 ----
print("🚀 3. 로컬 Vector DB 데이터 구조 파일 생성 중...")
guide_data = {
    "collection_name": "childcare_guide",
    "ids": [str(i) for i in range(len(chunks_texts))],
    "embeddings": embeddings,
    "documents": chunks_texts,
    "metadatas": [{"source": "영유아_문제행동지도_보육교사_지침서"} for _ in chunks_texts]
}

with open(GUIDE_OUTPUT, "w", encoding="utf-8") as wf:
    json.dump(guide_data, wf, ensure_ascii=False, indent=2)

if os.path.exists(CHECKPOINT_FILE):
    os.remove(CHECKPOINT_FILE)

print(f"✨ 완료: {GUIDE_OUTPUT}에 저장되었습니다.")