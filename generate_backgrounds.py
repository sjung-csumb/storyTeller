# generate_backgrounds.py
#
# Gemini(나노 바나나) 이미지 생성 모델로 streamlit_app_inline.py에서 쓸
# 스테이지별 배경 이미지 3장을 생성해서 static/ 폴더에 저장하는 1회성 스크립트입니다.
# 매 요청마다 생성하는 게 아니라, 이 스크립트를 한 번 실행해서 파일로 저장해두고
# 앱에서는 저장된 이미지를 그대로 불러다 씁니다.
#
# 준비:
#   pip install google-genai
#   export GEMINI_API_KEY="본인의 Gemini API 키"
#
# 실행:
#   python3 generate_backgrounds.py
#
# 주의:
#   아래 model 이름("gemini-2.5-flash-image")은 이 스크립트 작성 시점 기준입니다.
#   "나노 바나나 2"처럼 더 최신 모델이 나왔다면, Google AI Studio(https://aistudio.google.com)의
#   모델 목록에서 정확한 모델 ID를 확인해서 MODEL_NAME 값만 바꿔주면 됩니다.

import os
from pathlib import Path

from google import genai

MODEL_NAME = "gemini-2.5-flash-image"  # 필요 시 최신 "나노 바나나" 모델 ID로 교체

OUT_DIR = Path(__file__).parent / "static"
OUT_DIR.mkdir(exist_ok=True)

# 세 장 모두 같은 그림체(플랫 판타지 게임 배경 아트, 은은한 발광, 몰입감 있는 구도)로
# 통일되도록 스타일 문구를 공통으로 붙였습니다.
STYLE_SUFFIX = (
    " Digital painting, fantasy game background art style, cinematic lighting, "
    "glowing atmospheric light, rich color grading, no text, no characters, no UI, "
    "wide landscape composition, highly detailed illustration."
)

PROMPTS = {
    "bg_forest.png": (
        "A dense, majestic pine and birch forest seen from a slightly elevated angle, "
        "entrance to a deep magical forest, sunlight filtering through the canopy, "
        "vivid green and golden-yellow autumn leaves scattered among evergreens."
        + STYLE_SUFFIX
    ),
    "bg_cave.png": (
        "The entrance to a mysterious dungeon cave, glowing purple and blue magical light "
        "spilling from a stone archway deep inside, rocky cave walls covered in moss, "
        "moody nighttime atmosphere, a faint path leading toward the glowing doorway."
        + STYLE_SUFFIX
    ),
    "bg_vault.png": (
        "A hidden treasure vault at the heart of a dungeon, a glowing legendary storybook "
        "resting on a stone pedestal at the center, surrounded by piles of gold coins and gems, "
        "warm golden light beams radiating from the book, ancient stone chamber."
        + STYLE_SUFFIX
    ),
}


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("환경변수 GEMINI_API_KEY 를 먼저 설정해주세요.")

    client = genai.Client(api_key=api_key)

    for filename, prompt in PROMPTS.items():
        print(f"생성 중: {filename} ...")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
        )

        saved = False
        for part in response.candidates[0].content.parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                out_path = OUT_DIR / filename
                out_path.write_bytes(inline_data.data)
                print(f"  저장 완료: {out_path}")
                saved = True
                break

        if not saved:
            print(f"  ⚠️ {filename} 생성 실패 (이미지 데이터를 받지 못했습니다). 응답: {response}")

    print("\n모든 이미지 생성이 끝나면, static/ 폴더의 파일들을 확인한 뒤 알려주세요.")
    print("제가 streamlit_app_inline.py에 각 스테이지 배경으로 심어드리겠습니다.")


if __name__ == "__main__":
    main()
