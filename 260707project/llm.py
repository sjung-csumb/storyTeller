import os
import json
import json_repair
from openai import OpenAI
from dotenv import load_dotenv
from models import Child
from kb_retriever import get_retriever

load_dotenv()

UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY")
# Upstage Solar API compatibility with OpenAI client
client = OpenAI(
    api_key=UPSTAGE_API_KEY,
    base_url="https://api.upstage.ai/v1/solar"
)

def generate_fairy_tale(
    child: Child,
    appearance: str,
    personality: str,
    place: str,
    time_period: str,
    mood: str,
    problem_situation: str
) -> dict:
    """
    Call the Solar LLM API to generate a fairy tale based on the child's info and problem situation.
    Returns a dictionary containing the title and content_json.
    """
    if not UPSTAGE_API_KEY:
        # Fallback for testing without API key
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (API 키 없음)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False)
        }

    # Construct the prompt
    system_prompt = (
        "너는 아동 심리 발달을 돕는 전문 동화 작가야. "
        "주어진 아이의 성향과 교정해야 할 문제 상황을 바탕으로 짧고 교훈적이면서 재미있는 동화를 작성해줘. "
        "**가장 중요한 규칙: 동화는 반드시 기-승-전-결 구조를 갖춘 딱 4페이지로만 구성해야 해.**"
    )
    
    user_prompt = (
        f"주인공 이름: {child.name}\n"
        f"나이: {child.age}세\n"
        f"성별: {child.gender}\n"
        f"주인공 외형: {appearance}\n"
        f"주인공 성격: {personality}\n"
        f"배경 장소: {place}\n"
        f"배경 시대: {time_period}\n"
        f"동화 분위기: {mood}\n"
        f"교정이 필요한 문제 상황: {problem_situation}\n"
    )
        
    user_prompt += (
        "\n출력 형식은 반드시 순수한 JSON 형태여야 하며, 마크다운(```json)을 사용하지 마.\n"
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

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        
        result_str = response.choices[0].message.content.strip()
        
        # JSON 블록( { 부터 } 까지 )만 추출하여 마크다운이나 불필요한 텍스트 제거
        start_idx = result_str.find('{')
        end_idx = result_str.rfind('}')
        if start_idx != -1 and end_idx != -1:
            result_str = result_str[start_idx:end_idx+1]
            
        try:
            result_json = json.loads(result_str)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 에러: {e}")
            print(f"--- LLM이 반환한 원본 텍스트 ---\n{result_str}\n---------------------------------")
            raise e
            
        if isinstance(result_json, list):
            result_json = {
                "title": f"{child.name}의 모험",
                "cover_image_prompt": "A beautiful storybook cover art",
                "content": result_json
            }

        return {
            "title": result_json.get("title", f"{child.name}의 모험"),
            "cover_image_prompt": result_json.get("cover_image_prompt", f"A beautiful storybook cover art for a fairy tale titled {child.name}'s adventure"),
            "content_json": json.dumps(result_json.get("content", [{"page": 1, "text": result_str}]), ensure_ascii=False)
        }
    except Exception as e:
        print(f"LLM API Error: {e}")
        # Fallback gracefully
        return {
            "title": f"{child.name}의 모험 (생성 실패)",
            "cover_image_prompt": "A beautiful storybook cover art",
            "content_json": json.dumps([{"page": 1, "text": "동화를 생성하는 중 오류가 발생했습니다."}], ensure_ascii=False)
        }

def generate_fairy_tale_with_rag(
    child: Child,
    appearance: str,
    personality: str,
    place: str,
    time_period: str,
    mood: str,
    problem_situation: str,
    language: str = "ko"
) -> dict:
    """
    Call the Solar LLM API with RAG (Dynamic Few-shot).
    Retrieves similar past fairy tales from the KB and injects them as examples.
    """
    if not UPSTAGE_API_KEY:
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (RAG 모드)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False)
        }

    # Construct the query for KB retrieval
    query = (
        f"카테고리: {problem_situation}\n"
        f"대상 연령: {child.age}세\n"
        f"주인공 성격: {personality}\n"
    )
    
    retriever = get_retriever("data/formatted_val.jsonl")
    few_shot_examples = retriever.retrieve_few_shot(query, top_k=1)
    
    # 연령별 맞춤 지시문
    if child.age <= 4:
        age_rule = "3~4세 유아를 타겟으로 하므로, 아주 쉬운 어휘와 짧은 문장을 사용하고 의성어/의태어를 듬뿍 넣어서 아기자기하게 작성해."
    else:
        age_rule = "5~6세 아동을 타겟으로 하므로, 너무 유치하지 않게 조금 더 논리적인 인과관계와 성숙한 어휘를 사용하고, 스스로 생각할 수 있는 교훈을 담아줘."
        
    # 성별 맞춤 지시문 (아이의 성향이 최우선이나, 테마에 양념을 치는 용도)
    if child.gender == "남자":
        gender_rule = "스토리에 모험심을 자극하고 활동적인 전개(탐험, 문제 해결 등)를 살짝 섞어주면 좋아."
    elif child.gender == "여자":
        gender_rule = "스토리에 풍부한 감수성을 자극하고 판타지적 요소(마법, 요정, 아름다운 우정 등)를 살짝 섞어주면 좋아."
    else:
        gender_rule = "아이의 성향과 분위기에 맞추어 창의적으로 전개해."
        
    # 언어 맞춤 지시문 추가
    if language.lower() == "en":
        language_rule = "\n**[최우선 절대 규칙 - 언어]** 위 모든 내용과 RAG 참고 예시가 한국어이더라도, 네가 최종적으로 출력하는 'title'과 'text'는 **무조건 100% 완벽한 영미권 유아 동화 스타일의 영어(English)로 번역해서** 출력해야만 해! 절대로 한국어를 출력하지 마!"
    else:
        language_rule = ""

    # Construct the prompt
    system_prompt = (
        "너는 아동 심리 발달을 돕는 다정하고 창의적인 전문 구연동화 작가야. "
        "주어진 아이의 성향과 교정해야 할 문제 상황을 바탕으로 짧고 교훈적이면서 재미있는 동화를 작성해줘. "
        "**[이야기(text) 작성 규칙]**\n"
        "0. **[치명적 규칙]** 대화체 등 모든 텍스트(text) 작성 시 절대로 쌍따옴표(\")를 사용하지 마! 무조건 작은따옴표(')만 사용해! (JSON 파싱 에러 방지)\n"
        f"1. {age_rule}\n"
        f"2. {gender_rule}\n"
        "3. 문장 끝에는 마침표(.)뿐만 아니라 느낌표(!)나 물음표(?)를 적절히 혼용해서 리듬감을 살려줘.\n"
        f"4. **[자연스러운 구어체]** 대화체는 한국 부모와 아이가 실제로 쓰는 자연스럽고 따뜻한 일상 구어체를 사용해 (예: '어떤 기분이야?' 대신 '우리 {child.name} 지금 기분이 어때?').\n"
        "5. **[어휘와 직관적 비유]** 번역투의 어른스러운 비유를 피하고, 의성어와 의태어를 풍부하게 사용해. 특히 상황을 설명할 때는 주변 사물이나 동물, 자연 현상에 빗댄 아이 친화적이고 직관적인 비유를 그 동화의 내용에 맞게 창작해서 사용해 (예: 마음이 쿵쿵 뛰는 것을 묘사할 때 '북을 치는 것 같아요' 등).\n"
        "6. **[감정 고조 및 리듬감]** 아이의 감정을 묘사할 때 단순히 '슬펐어요'가 아니라, 신체적 반응이나 구체적 행동으로 묘사해. 또한 이야기 흐름 속에 아이들이 따라 부를 수 있는 입에 착 달라붙는 짧고 리듬감 있는 문구를 창작해서 반복 삽입해.\n"
        "7. **[문장 흐름 및 극본 금지]** 대화 시 '나영: ~', '타요: ~' 같은 대본 형식으로 쓰지 마. 반드시 '나영이가 방긋 웃으며 말했어요.' 처럼 부드럽고 다정한 서술형 동화 문체로 작성해.\n"
        "8. **[외형 묘사 금지]** 주인공의 옷 색깔이나 머리스타일 같은 외형 묘사는 'image_prompt'에만 적고, 이야기(text) 본문에는 억지로 끼워 넣지 마!\n"
        "**[전체 구조 및 개연성 규칙]**\n"
        "9. **[분량 및 개연성 필수]** 각 페이지의 텍스트는 절대로 한 줄로 짧게 끝내지 말고, 최소 2~3문장 이상으로 풍성하게 써! 문제가 해결되는 과정을 뚝딱 넘기지 말고, 아이가 왜 그런 행동을 했는지 속마음을 풀어주고 달래주는 감정선을 아주 구체적으로 개연성 있게 묘사해.\n"
        "10. 자연스러운 스토리 흐름: 4페이지 동안 '문제 발생 -> 마음 알아주기 -> 깨달음 -> 교훈'의 흐름이 물 흐르듯 이어지도록 구성해. **단, 동화 내용 안에 '**문제 발생**', '**교훈**' 같은 분석적인 단어는 절대 직접 적지 마!** 순수하게 동화만 적어야 해.\n"
        "11. **[실생활 연계 마무리]** 만약 꿈속 모험 이야기라면, 마지막 4페이지에서는 반드시 잠에서 깨어나 현실로 돌아오는 장면을 넣어. 그리고 동화 속에서 배운 교훈을 현실에서 부모님께 자신의 언어로 말하며 실천하고, 부모님께 따뜻하게 안기며 칭찬받는 모습으로 현실과 완벽하게 연계시켜서 마무리해. (절대 상관없는 이야기를 지어내지 마!)"
        f"{language_rule}"
    )
    
    user_prompt = (
        f"주인공 이름: {child.name}\n"
        f"나이: {child.age}세\n"
        f"성별: {child.gender}\n"
        f"주인공 외형: {appearance}\n"
        f"주인공 성격: {personality}\n"
        f"배경 장소: {place}\n"
        f"배경 시대: {time_period}\n"
        f"동화 분위기: {mood}\n"
        f"교정이 필요한 문제 상황: {problem_situation}\n"
    )
        
    user_prompt += (
        "\n출력 형식은 반드시 순수한 JSON 형태여야 하며, 마크다운(```json)을 사용하지 마.\n"
        "다음 키를 포함해야 해:\n"
        "1. 'title': 동화의 제목 (문자열)\n"
        "2. 'cover_image_prompt': 동화책 표지를 위한 영문 그림 프롬프트. 반드시 주인공의 나이, 성별, 외형 묘사(영어)를 포함할 것.\n"
        "3. 'content': 페이지별 이야기 배열. 각 페이지는 'page'(숫자), 'text'(문자열), 'image_prompt'(영문 문자열) 키를 가져야 해.\n"
        "   - **[매우 중요]** 'image_prompt'는 무조건 영어로 작성해. 절대로 'Once upon a time' 같은 동화 문체나 감성적인 어휘를 넣지 마!\n"
        "   - 프롬프트 구조: [토씨 하나 안 틀린 동일한 주인공 묘사] + [각 페이지에 맞는 구체적인 행동과 오브젝트] + [심플한 배경 묘사] + [, consistent character design, simple background, in watercolor children's book illustration style]\n"
        "   - **주의 1 (캐릭터 일관성):** 네가 주인공 외형(나이, 성별, 머리, 옷)만 짧게 영어로 번역해서 고정 문구(예: 'A 5-year-old boy, (bald head, red shirt, yellow shorts), ')를 하나 만들어. 그리고 **이 짧은 고정 문구 하나만** 모든 페이지의 image_prompt 맨 앞에 딱 한 번씩만 붙여넣어! 절대 이전 페이지의 배경이나 행동 묘사까지 통째로 복붙해서 중복 문장을 만들지 마! 각 페이지마다 아이의 행동(action)은 달라야 해.\n"
        "   - **주의 2:** 철저하게 시각적이고 객관적인 묘사(행동, 사물) 위주로 작성해. 배경이 너무 복잡해지면 캐릭터 디자인이 망가지므로 배경 묘사는 핵심만 단순하게(simple) 적어.\n"
        "   - **주의 3 (스타일 고정):** 내가 제공한 참고 예시에 이 문구가 없더라도 무시하고, 네가 출력하는 모든 image_prompt 마지막에는 무조건 `, consistent character design, simple background, in watercolor children's book illustration style`을 필수로 붙여야만 해!\n"
    )
    
    if few_shot_examples:
        user_prompt += "\n--- 참고할 수 있는 우수 동화 예시 (아래 예시들의 텍스트 톤과 구조만 모방하되, 예시 속 이름(예: 짱구)을 절대 베끼지 말고 무조건 주어진 주인공 이름만 사용할 것!) ---\n"
        for idx, ex in enumerate(few_shot_examples):
            user_prompt += f"예시 {idx+1}:\n{ex}\n"
    else:
        user_prompt += (
            "\n--- 출력 예시 (이 구조와 패턴을 엄격하게 지켜!) ---\n"
            "{\n"
            f"  \"title\": \"{child.name}의 신나는 모험\",\n"
            "  \"cover_image_prompt\": \"A 5-year-old boy, (bald head, red shirt, yellow shorts), looking happy, in watercolor children's book illustration style\",\n"
            "  \"content\": [\n"
            f"    {{\"page\": 1, \"text\": \"엄마, {child.name}는 오늘 신나게 놀았어요!\", \"image_prompt\": \"A 5-year-old boy, (bald head, red shirt, yellow shorts), running in a living room, consistent character design, simple background, in watercolor children's book illustration style\"}}\n"
            "  ]\n"
            "}\n"
        )

    try:
        response = client.chat.completions.create(
            model="solar-pro3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        
        result_str = response.choices[0].message.content.strip()
        
        start_idx = result_str.find('{')
        end_idx = result_str.rfind('}')
        if start_idx != -1 and end_idx != -1:
            result_str = result_str[start_idx:end_idx+1]
            
        try:
            result_json = json_repair.loads(result_str)
        except Exception as e:
            print(f"❌ JSON 파싱 에러 (RAG): {e}")
            raise e
            
        if isinstance(result_json, list):
            result_json = {
                "title": f"{child.name}의 모험 (RAG)",
                "cover_image_prompt": "A beautiful storybook cover art",
                "content": result_json
            }

        return {
            "title": result_json.get("title", f"{child.name}의 모험 (RAG)"),
            "cover_image_prompt": result_json.get("cover_image_prompt", "A beautiful storybook cover art"),
            "content_json": json.dumps(result_json.get("content", [{"page": 1, "text": result_str}]), ensure_ascii=False)
        }
    except Exception as e:
        print(f"LLM API Error (RAG): {e}")
        return {
            "title": f"{child.name}의 모험 (RAG 실패)",
            "cover_image_prompt": "A beautiful storybook cover art",
            "content_json": json.dumps([{"page": 1, "text": "RAG 동화를 생성하는 중 오류가 발생했습니다."}], ensure_ascii=False)
        }
