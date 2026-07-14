import json
import os
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
OS_API_KEY = os.environ["UPSTAGE_API_KEY"]
PDF_PATH = "C:/YHM/문제행동 지도를 위한 지침서.pdf"
OUTPUT_DIR = "./chroma_db"
MARKDOWN_OUTPUT = os.path.join(OUTPUT_DIR, "guide_markdown.md")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def request_document_parse(pdf_path):
    boundary = "----ClaudeBoundary"
    with open(pdf_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\ndocument-parse\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="output_formats"\r\n\r\n[\'markdown\']\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="doc.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        "https://api.upstage.ai/v1/document-digitization/async",
        data=body,
        headers={
            "Authorization": f"Bearer {OS_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        method="POST"
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))["request_id"]


def poll_result(request_id):
    status_url = f"https://api.upstage.ai/v1/document-digitization/requests/{request_id}"
    while True:
        req = urllib.request.Request(status_url, headers={"Authorization": f"Bearer {OS_API_KEY}"})
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"❌ 상태 조회 중 에러: {e}\n{e.read().decode('utf-8')}")
            raise

        status = data.get("status")
        print(f"⏳ 파싱 상태: {status}")

        if status == "completed":
            return data
        elif status == "failed":
            raise RuntimeError(f"파싱 실패: {data}")

        time.sleep(10)


def download_batch_results(status_data):
    """completed 상태 응답에서 각 배치의 markdown을 다운로드해 하나로 합칩니다."""
    batches = status_data.get("batches", [])
    print(f"📦 총 {len(batches)}개 배치 발견. 다운로드 시작...")

    # 페이지 순서 보장을 위해 정렬 (배치 순번 필드 기준)
    batches_sorted = sorted(batches, key=lambda b: b.get("id", b.get("batch_id", 0)))

    all_markdown = []
    for i, batch in enumerate(batches_sorted):
        if batch["status"] != "completed":
            print(f"⚠️ 배치 {i} 상태가 completed가 아님: {batch['status']} → 건너뜀")
            continue

        download_url = batch["download_url"]
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req) as res:
            batch_data = json.loads(res.read().decode("utf-8"))

        batch_markdown = batch_data.get("content", {}).get("markdown", "")
        all_markdown.append(batch_markdown)

        if (i + 1) % 10 == 0 or (i + 1) == len(batches_sorted):
            print(f"🔄 배치 다운로드 진행률: {i + 1}/{len(batches_sorted)}")

    return "\n\n".join(all_markdown)


print("📄 1. PDF Document Parse 요청 시작 (616페이지, async 방식)...")
try:
    request_id = request_document_parse(PDF_PATH)
    print(f"✅ 요청 접수됨. request_id: {request_id}")
except urllib.error.HTTPError as e:
    print(f"❌ 요청 실패: {e}\n{e.read().decode('utf-8')}")
    exit()

print("⏳ 2. 파싱 완료까지 대기 중 (페이지가 많아 수 분 소요될 수 있습니다)...")
result = poll_result(request_id)

print("📥 3. 완료된 배치 결과 다운로드 중 (URL은 15분간만 유효하므로 바로 진행합니다)...")
markdown_text = download_batch_results(result)

print(f"✅ 파싱 완료! 마크다운 총 {len(markdown_text)}자 확보")

with open(MARKDOWN_OUTPUT, "w", encoding="utf-8") as f:
    f.write(markdown_text)

print(f"✨ 저장 완료: {MARKDOWN_OUTPUT}")
print("👉 이 파일을 열어서 내용이 잘 파싱되었는지 확인해주세요.")