import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY")
client = OpenAI(
    api_key=UPSTAGE_API_KEY,
    base_url="https://api.upstage.ai/v1/solar"
)

def process_kaggle_data(input_file="AI.json", output_file="data/formatted_kaggle.jsonl", max_samples=5, skip_samples=0):
    """
    Kaggle AI.json 데이터를 읽어와서 안전한 스토리를 필터링하고,
    Solar Pro API를 이용해 우리 RAG 포맷으로 번역 및 변환합니다.
    (테스트를 위해 기본적으로 5개만 변환합니다)
    """
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Total stories loaded: {len(data)}")
    
    valid_stories = []
    for item in data:
        # 아동용 동화에 부적절한(Safety violations가 있는) 스토리는 필터링
        safety = item.get("safety_violations", {})
        if safety.get("present") == True:
            continue
            
        # 13+ 등급이 아닌 유아/어린이 대상이거나, 나이 조건이 없는 것 선별
        age = item.get("age_group", "")
        if "13+" in age or "18+" in age:
            continue
            
        valid_stories.append(item.get("story"))

    print(f"Safe & valid stories found: {len(valid_stories)}")
    
    processed_count = 0
    with open(output_file, 'a', encoding='utf-8') as out_f:
        for story in valid_stories[skip_samples : skip_samples + max_samples]:
            print(f"\nProcessing story {processed_count + 1}/{max_samples}...")
            
            prompt = (
                "너는 아동 심리 발달을 돕는 번역가 겸 동화 작가야.\n"
                "다음 영문 스토리를 한국어로 번역하고, 유아~어린이가 읽기 좋게 교훈적으로 다듬어줘.\n"
                "반드시 우리가 사용하는 기-승-전-결 4페이지 형식의 JSON으로만 출력해야 해 (마크다운 사용 금지).\n\n"
                f"[원본 영문 스토리]\n{story}\n\n"
                "[출력 JSON 형식]\n"
                "1. 'title': 동화 제목 (한국어)\n"
                "2. 'cover_image_prompt': 표지 이미지 프롬프트 (영어)\n"
                "3. 'content': [{'page': 1, 'text': '한국어 내용', 'image_prompt': '영어 프롬프트'}, ... 총 4페이지]\n"
            )
            
            try:
                response = client.chat.completions.create(
                    model="solar-pro3",
                    messages=[{"role": "user", "content": prompt}],
                )
                
                result_str = response.choices[0].message.content.strip()
                
                # JSON 추출
                start_idx = result_str.find('{')
                end_idx = result_str.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    result_str = result_str[start_idx:end_idx+1]
                
                parsed_json = json.loads(result_str)
                
                # RAG용 지식 베이스 포맷(User-Assistant 대화쌍)으로 래핑
                kb_format = {
                    "messages": [
                        {"role": "user", "content": f"동화 카테고리: 일반\n주인공 성격: 다양함\n대상 연령: 어린이"},
                        {"role": "assistant", "content": json.dumps(parsed_json, ensure_ascii=False)}
                    ]
                }
                
                out_f.write(json.dumps(kb_format, ensure_ascii=False) + "\n")
                out_f.flush()
                print("[SUCCESS] 성공적으로 변환하여 저장했습니다!")
                processed_count += 1
                
            except Exception as e:
                print(f"[ERROR] 변환 실패: {e}")

if __name__ == "__main__":
    # 기존에 총 600개가 변환되었으므로 600개를 건너뛰고 남은 500개를 추가 변환합니다.
    process_kaggle_data(input_file="AI.json", output_file="data/formatted_kaggle.jsonl", max_samples=500, skip_samples=600)
