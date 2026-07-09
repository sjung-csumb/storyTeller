import json
import re

SYSTEM_PROMPT = (
    "너는 아동 심리 발달을 돕는 전문 동화 작가야. "
    "주어진 아이의 성향과 교정해야 할 문제 상황을 바탕으로 짧고 교훈적이면서 재미있는 동화를 작성해줘. "
    "**가장 중요한 규칙: 동화는 반드시 기-승-전-결 구조를 갖춘 딱 4페이지로만 구성해야 해.**\n\n"
    "출력 형식은 반드시 순수한 JSON 형태여야 하며, 마크다운(```json)을 사용하지 마.\n"
    "다음 키를 포함해야 해:\n"
    "1. 'title': 동화의 제목 (문자열)\n"
    "2. 'cover_image_prompt': 동화책 표지를 위한 영문 그림 프롬프트. 반드시 주인공의 나이, 성별, 외형 묘사(영어)를 포함할 것.\n"
    "3. 'content': 페이지별 이야기 배열. 각 페이지는 'page'(숫자), 'text'(문자열), 'image_prompt'(영문 문자열) 키를 가져야 해.\n"
    "   - **[매우 중요]** 'image_prompt'는 무조건 영어로 작성해.\n"
    "   - 프롬프트 구조: [번역된 주인공 외형 고정] + [해당 페이지의 구체적인 행동과 배경]\n"
    "   - **주의:** 외형 묘사는 내가 입력해 주는 '주인공 외형' 정보를 바탕으로 네가 직접 영어로 번역해서 고정해둬야 해! (절대 아래 예시의 overalls나 wooden stick을 베껴 쓰면 안 됨! 예시는 그냥 예시일 뿐이야)\n"
    "   - 행동(action)이나 배경(background)은 페이지 이야기 상황에 맞게 매번 다르게 적어야 해!\n"
    "예시:\n"
    "{\n"
    "  \"title\": \"양치기 소년\",\n"
    "  \"cover_image_prompt\": \"A beautiful storybook cover art featuring a 4-year-old toddler boy in overalls holding a wooden stick...\",\n"
    "  \"content\": [\n"
    "    {\"page\": 1, \"text\": \"첫 번째 페이지 이야기...\", \"image_prompt\": \"A 4-year-old toddler boy in overalls holding a wooden stick, sleeping under a big tree in a green grassy field\"},\n"
    "    {\"page\": 2, \"text\": \"두 번째 페이지 이야기...\", \"image_prompt\": \"A 4-year-old toddler boy in overalls holding a wooden stick, running down the hill in panic\"}\n"
    "  ]\n"
    "}"
)

def chunk_text(text, num_chunks=4):
    """텍스트를 문장 단위로 분할하여 대략 4개의 페이지로 나눕니다."""
    sentences = re.split(r'(?<=[.!?]) +|\n+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) < num_chunks:
        # 문장이 4개도 안 되면 그냥 나눌 수 있는 만큼 나눔
        chunks = sentences + [""] * (num_chunks - len(sentences))
    else:
        chunk_size = len(sentences) / num_chunks
        chunks = []
        for i in range(num_chunks):
            start = int(i * chunk_size)
            end = int((i + 1) * chunk_size) if i < num_chunks - 1 else len(sentences)
            chunks.append(" ".join(sentences[start:end]))
    return chunks

def process_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as fin, \
         open(output_file, 'w', encoding='utf-8') as fout:
         
        for line in fin:
            if not line.strip(): continue
            data = json.loads(line)
            prompt_text = data['prompt']
            completion_text = data['completion']
            
            # 제목 추출 시도
            title_match = re.search(r"동화 제목:\s*(.*)", prompt_text)
            title = title_match.group(1).strip() if title_match else "무제 동화"
            
            # 등장인물 추출 시도 (이미지 프롬프트용)
            char_match = re.search(r"주요 등장인물:\s*(.*)", prompt_text)
            characters = char_match.group(1).strip() if char_match else "characters"
            # 번역 API를 쓰면 너무 오래 걸리니 학습용 가상 영어 프롬프트 뼈대 삽입
            base_img_prompt = f"A beautiful watercolor illustration of {characters}"
            
            # 텍스트를 4장으로 분할
            pages_text = chunk_text(completion_text, 4)
            
            # 우리가 원하는 JSON 구조 조립
            target_json = {
                "title": title,
                "cover_image_prompt": f"A beautiful storybook cover art for {title}",
                "content": []
            }
            
            for idx, p_text in enumerate(pages_text):
                target_json["content"].append({
                    "page": idx + 1,
                    "text": p_text,
                    "image_prompt": f"{base_img_prompt}, scene {idx + 1}"
                })
                
            # Chat 포맷 완성
            chat_format = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_text},
                    {"role": "assistant", "content": json.dumps(target_json, ensure_ascii=False)}
                ]
            }
            
            fout.write(json.dumps(chat_format, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    print("데이터 전처리를 시작합니다...")
    process_file("data/train.jsonl", "data/formatted_train.jsonl")
    print("전처리 완료! -> data/formatted_train.jsonl 생성됨")
