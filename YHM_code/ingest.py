import json
import os
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
OS_API_KEY = os.environ["UPSTAGE_API_KEY"]
INPUT_FILE = "formatted_train.jsonl"
OUTPUT_DIR = "./chroma_db"
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("⏳ 1. 최종본 데이터셋(formatted_train.jsonl) 분석 및 텍스트 정제 시작...")
chunks_texts = []
chunks_metadatas = []

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        data = json.loads(line)
        user_content = data["messages"][0]["content"]
        assistant_content = data["messages"][1]["content"]

        clean_text = str(assistant_content).strip()
        max_chars = 800
        for i in range(0, len(clean_text), max_chars):
            chunk = clean_text[i:i + max_chars]
            if chunk:
                chunks_texts.append(chunk)
                chunks_metadatas.append({"query_format": str(user_content)})

print(f"📚 데이터 정제 완료! 총 {len(chunks_texts)}개의 조각으로 분할되었습니다.")

# ---- 체크포인트 불러오기 (이전에 중단된 지점부터 이어서 진행) ----
embeddings = []
start_idx = 0
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as cf:
        ckpt = json.load(cf)
        embeddings = ckpt["embeddings"]
        start_idx = len(embeddings)
    print(f"🔁 체크포인트 발견! {start_idx}번째부터 이어서 진행합니다.")

url = "https://api.upstage.ai/v1/solar/embeddings"
headers = {
    "Authorization": f"Bearer {OS_API_KEY}",
    "Content-Type": "application/json"
}

print("🧠 2. Upstage API 연동하여 Solar 임베딩 추출 시작...")

REQUEST_DELAY = 0.5      # 요청 사이 기본 대기(초). 429가 계속 나면 1.0~2.0으로 늘려보세요.
MAX_RETRIES = 5

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
                wait_time = 2 ** attempt  # 2, 4, 8, 16, 32초로 점점 길게 대기
                print(f"⏳ 429 Too Many Requests (위치 {idx}, 시도 {attempt}/{MAX_RETRIES}) → {wait_time}초 대기 후 재시도...")
                time.sleep(wait_time)
                continue
            else:
                err_body = e.read().decode("utf-8")
                print(f"❌ 임베딩 요청 중 에러 발생 (위치 {idx}): {e}\n서버 응답: {err_body}")
                # 여기까지 완료된 것만 체크포인트로 저장하고 종료
                with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
                    json.dump({"embeddings": embeddings}, cf)
                exit()
    else:
        print(f"❌ 위치 {idx}: 재시도 {MAX_RETRIES}회 모두 실패. 잠시 후 스크립트를 다시 실행해 이어서 진행하세요.")
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
            json.dump({"embeddings": embeddings}, cf)
        exit()

    # 진행 상황 출력 + 주기적 체크포인트 저장
    if (idx + 1) % 50 == 0 or (idx + 1) == len(chunks_texts):
        print(f"🔄 진행률: {idx + 1}/{len(chunks_texts)} 완료...")
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
            json.dump({"embeddings": embeddings}, cf)

    time.sleep(REQUEST_DELAY)  # 요청 사이 기본 대기 (레이트리밋 예방)

print(f"✅ 총 {len(embeddings)}개 조각 임베딩 완료!")

print("🚀 3. 로컬 Vector DB 데이터 구조 파일 생성 중...")
chroma_data = {
    "collection_name": "fairy_tales",
    "ids": [str(idx) for idx in range(len(chunks_texts))],
    "embeddings": embeddings,
    "documents": chunks_texts,
    "metadatas": chunks_metadatas
}

with open(os.path.join(OUTPUT_DIR, "local_vector_index.json"), "w", encoding="utf-8") as wf:
    json.dump(chroma_data, wf, ensure_ascii=False, indent=2)

# 최종 완료 후 체크포인트 파일은 삭제(선택)
if os.path.exists(CHECKPOINT_FILE):
    os.remove(CHECKPOINT_FILE)

print(f"✨ 완료: '{OUTPUT_DIR}/local_vector_index.json'에 저장되었습니다.")