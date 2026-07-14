import os
import time
import requests
import urllib.parse

# 캐릭터의 외모 일관성을 위한 고정 프롬프트 (MVP 수준)
# 수채화 기반의 따뜻한 동화책 삽화 + 명확한 한국인/동아시아인 외모 강제
BASE_CHARACTER_PROMPT = ", authentic Korean toddler, East Asian facial features, black hair, dark eyes, cute flat nose, beautiful watercolor children's book illustration, soft pastel colors, storybook art style, whimsical, cozy and warm atmosphere"

def generate_page_image(image_prompt: str, fairytale_id: int, page_num: int) -> str:
    """
    이미지를 생성하고 static/images 폴더에 저장한 뒤,
    서빙 가능한 URL 경로를 반환합니다.
    """
    # LLM이 완벽한 영어 프롬프트를 만들어주므로, 기존 한글 외형 추가 부분을 제거하고 기본 화풍만 덧붙임
    full_prompt = f"{image_prompt}" + BASE_CHARACTER_PROMPT
    print(f"[IMG] 이미지 생성 중 (동화 {fairytale_id} - Page {page_num})...")
    
    # URL 인코딩 (공백 등을 안전한 문자로 변환)
    encoded_prompt = urllib.parse.quote(full_prompt)
    
    # Pollinations AI URL (가입 불필요, API Key 불필요, 완전 무료)
    # 동화 ID를 seed로 사용하여 동화 내 그림 스타일의 일관성을 높입니다.
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={fairytale_id}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                # 파일명 생성 및 저장
                filename = f"{fairytale_id}_page_{page_num}.png"
                save_path = os.path.join("static", "images", filename)
                
                with open(save_path, "wb") as f:
                    f.write(response.content)
                    
                print(f"[SUCCESS] 그림 생성 완료! '{save_path}'")
                
                # FastAPI에서 접근할 URL 경로 반환
                return f"/static/images/{filename}"
            else:
                wait_time = 10
                print(f"[WARN] 이미지 생성 에러: HTTP {response.status_code}. {wait_time}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                
        except Exception as e:
            print(f"[ERROR] 네트워크 에러: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
                
    print("[ERROR] 이미지 생성 실패: 최대 재시도 횟수 초과. 더미 이미지를 반환합니다.")
    return "https://placehold.co/1024x1024/29160a/cca97e?text=Image+Not+Available"
