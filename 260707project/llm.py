import os
import json
import json_repair
import asyncio
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_upstage import ChatUpstage
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, START, END

from models import Child
from kb_retriever import get_retriever

load_dotenv()

UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY")

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
    if not UPSTAGE_API_KEY:
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (API 키 없음)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False)
        }

    system_prompt = (
        "너는 아동 심리 발달과 행동교정을 돕는 전문 동화 작가야. "
        "주어진 아이의 성향과 교정해야 할 문제 상황을 바탕으로 짧고 교훈적이면서 재미있는 동화를 작성해줘. "
        "**가장 중요한 규칙: 동화는 반드시 기-승-전-결 구조를 갖춘 딱 4페이지로만 구성해야 해.**"
    )
    
    user_prompt = (
        f"주인공 이름: {child.name}\n나이: {child.age}세\n성별: {child.gender}\n"
        f"주인공 외형: {appearance}\n주인공 성격: {personality}\n배경 장소: {place}\n"
        f"배경 시대: {time_period}\n동화 분위: {mood}\n교정이 필요한 문제 상황: {problem_situation}\n"
        "\n출력 형식은 반드시 순수한 JSON 형태여야 하며...\n(생략)"
    )

    try:
        response = client.chat.completions.create(
            model="solar-pro",
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
            
        result_json = json.loads(result_str)
        return {
            "title": result_json.get("title", f"{child.name}의 모험"),
            "cover_image_prompt": result_json.get("cover_image_prompt", "A beautiful storybook cover art"),
            "content_json": json.dumps(result_json.get("content", [{"page": 1, "text": result_str}]), ensure_ascii=False)
        }
    except Exception as e:
        print(f"LLM API Error: {e}")
        return {
            "title": f"{child.name}의 모험 (생성 실패)",
            "cover_image_prompt": "A beautiful storybook cover art",
            "content_json": json.dumps([{"page": 1, "text": "동화 생성 오류"}], ensure_ascii=False)
        }


# =========================================================================
# 2. LangGraph 기반 Multi-Agent RAG 로직
# =========================================================================

# 스키마 정의
class StoryPage(BaseModel):
    page: int = Field(description="페이지 번호 (1~4)")
    text: str = Field(description="이 페이지의 이야기 내용 텍스트")
    image_prompt: str = Field(description="이 페이지를 위한 영문 DALL-E 이미지 프롬프트")

class StoryFormat(BaseModel):
    title: str = Field(description="동화의 제목")
    cover_image_prompt: str = Field(description="동화책 표지를 위한 영문 이미지 프롬프트")
    content: List[StoryPage] = Field(description="각 페이지 정보 배열")

class GraphState(TypedDict):
    child_info: Dict[str, Any]
    language: str
    rag_context: str
    guide_text: str
    draft_ko: str
    feedback: Optional[str]
    revision_count: int
    final_text: str
    final_json: str

# 랭체인 업스테이지 최신 모델
chat_llm = ChatUpstage(model="solar-pro2")

# --- Nodes ---

def retrieve_node(state: GraphState) -> GraphState:
    child = state["child_info"]
    problem = child.get("problem_situation", "")
    
    retriever = get_retriever()
    query = f"아이의 문제 행동: {problem}\n아이의 성향: {child.get('personality')}\n"
    few_shot_results = retriever.retrieve_few_shot(query, top_k=1)
    example_results = retriever.retrieve_example(query, top_k=1)
    
    rag_context = ""
    guide_text = ""
    if few_shot_results:
        raw_guide = few_shot_results[0]
        rag_context += f"--- [보건복지부 아동 심리 전문가 지침] ---\n{raw_guide}\n\n위 지침을 참고하여, 아이의 행동 교정을 돕는 구체적인 대안 행동이 동화 속에 자연스럽게 포함되도록 작성해.\n\n"
        guide_text = ""
        
    if example_results:
        rag_context += f"--- [모범 동화 예시 (스타일/분량 참고용)] ---\n{example_results[0]}\n\n위 모범 예시의 문체, 문장 길이, 4페이지 분할 구조를 적극 참고해. 단, 예시가 JSON 형태더라도 너는 절대로 JSON 포맷으로 출력하지 말고, '순수한 텍스트 문단'으로만 4개의 단락(각 페이지)을 작성해.\n"
        
    return {"rag_context": rag_context, "guide_text": guide_text, "revision_count": 0}

def draft_node(state: GraphState) -> GraphState:
    child = state["child_info"]
    age = child.get("age", 4)
    gender = child.get("gender", "무관")
    name = child.get("name", "아이")
    
    if age <= 3:
        vocab_rule = f"입력된 {age}세 아동의 인지 수준에 맞춰 '포탈' 대신 '비밀 문' 등 아주 쉽고 직관적인 단어를 써. 영유아의 흥미를 끌 수 있도록 각 페이지마다 '사각사각', '몽글몽글' 같은 생동감 넘치는 의성어/의태어를 2개 이상씩 듬뿍 포함해. 특히 배경이나 문맥에서 '유치원'이라는 단어는 절대 쓰지 말고 무조건 '어린이집'으로 고정해."
    elif age == 4:
        vocab_rule = f"입력된 {age}세 아동의 인지 수준에 맞춰 '포탈' 대신 '비밀 문' 등 아주 쉽고 직관적인 단어를 써. 영유아의 흥미를 끌 수 있도록 각 페이지마다 '사각사각', '몽글몽글' 같은 생동감 넘치는 의성어/의태어를 2개 이상씩 듬뿍 포함해."
    else:
        vocab_rule = f"입력된 {age}세 아동의 어휘 수준에 맞춘 단어와 문장 구조를 사용해. 동화가 너무 유치해지지 않도록 각 페이지마다 연령대에 맞는 적절한 의성어/의태어를 1개 정도만 자연스럽게 포함해."
    length_rule = "아동이 읽기 편하도록 1쪽은 자유롭게 작성하되, 2쪽, 3쪽, 4쪽의 텍스트는 각각 무조건 정확히 '4문장'으로만 고정해서 작성해."
    resolution_rule = "조력자(부모, 코치, 선생님 등)의 따뜻한 스킨십이나 '어떻게 하면 좋을까?'라는 질문을 통해 아이 스스로 대안을 찾고 안정을 얻도록 유도해."

    lang_val = state.get("language", "ko").lower()
    if lang_val == "en":
        lang_rule = "미국의 양육자와 아이가 일상에서 쓰는 다정하고 자연스러운 구어체를 사용해. **반드시 이야기 전체 텍스트를 영문(English)으로 작성해!**"
    else:
        lang_rule = "한국의 양육자와 아이가 일상에서 쓰는 다정하고 자연스러운 구어체(~해요, ~했어요)를 사용해. 한국어로 작성해."

    if gender == "남자":
        gender_rule = "스토리에 모험심을 자극하고 활동적인 전개(탐험, 문제 해결 등)를 살짝 섞어주면 좋아."
    elif gender == "여자":
        gender_rule = "풍부한 감수성을 자극하고 판타지적 요소(마법, 요정 등)를 살짝 섞어주면 좋아."
    else:
        gender_rule = "아이의 성향에 맞추어 전개해."
        
    system_prompt = (
        "🚨 CRITICAL RULE: 이 동화는 반드시 4페이지(단락)로 끝나야 합니다. 5페이지나 6페이지를 절대로 생성하지 마십시오!\n\n"
        "너는 아동 심리 발달을 돕는 다정하고 창의적인 구연동화 작가야. "
        "주어진 아이의 성향과 문제 상황을 바탕으로, 아이의 행동 개선과 올바른 습관 형성을 돕는 4쪽짜리 맞춤형 동화를 제작해줘.\n"
        "**[사용자 입력값 해석 및 치환 규칙]**\n"
        "1. [문제 상황]에 '내 말을 안 들어서 실망했다'고 적혀 있다면: 아이가 그 행동을 하지 않았을 때 현실(어린이집 등)에서 겪게 될 '실제적 불편함이나 결과'(예: 내일 준비물이 없으면 네가 당황할 거야)를 인지시켜주는 방향으로 치환해.\n"
        "2. [문제 상황]에 '거짓말을 고쳐달라'고 적혀 있다면: 거짓말을 징벌하는 서사는 피하고, '거짓말을 하지 않고 솔직하게 말했을 때 얻는 용기와 칭찬(긍정적 강화)'에 초점을 맞춰 전개해.\n\n"
        "**[이야기 작성 필수 규칙]**\n"
        "1. **[사실관계 및 장소 강제 보존]** [문제 상황]의 사실관계를 왜곡하지 마. [배경(장소)]을 무조건 이야기의 메인 무대로 사용해.\n"
        "2. **[문장 부호 및 따옴표 규칙]** 모든 문장은 마침표(.), 물음표(?), 느낌표(!)로 완벽하게 끝맺어. 텍스트 작성 시 쌍따옴표(\")는 절대 금지! 대화는 무조건 작은따옴표(')만 사용해.\n"
        f"3. **[주인공]** 주인공 이름은 '{name}'(으)로 고정해.\n"
        f"4. **[문체 및 어투]** {vocab_rule} {gender_rule} {lang_rule} 기계적인 번역투나 딱딱한 문장은 절대 금지!\n"
        f"5. **[분량 조절]** {length_rule}\n"
        f"6. **[기승전결 서사 및 결말 템플릿]** 1쪽(배경 및 호기심 유발) -> 2쪽(문제 행동 발생 및 조력자의 공감) -> 3쪽(지침을 활용한 대안 행동 시도) -> 4쪽(행동 변화 다짐) 구조로 전개해. 해결 과정에서는 {resolution_rule}\n"
        "   **[4쪽 결말 유연화 템플릿]** 꿈이면 깨어나 안기고, 현실이면 조력자와 훈훈하게 마무리해.\n"
        "7. **[정서적 협박 금지 및 100% 수용]** 아이에게 '엄마가 슬프다, 실망했다, 마음이 아프다'는 부정적 감정을 무기로 행동을 통제하지 마. 또한 아이의 잘못을 무섭게 추궁(~했지?)하거나 지적하지 말고, '귀찮았구나'라며 아이의 감정을 100% 수용(Validate)한 후 긍정적 대안 행동과 칭찬(긍정적 자아 강화)으로 유도해.\n"
        "8. **[놀이식 행동 시뮬레이션 필수 포함]** 문제 해결 과정(가방 싸기, 양치 등)을 지루한 숙제가 아닌 사물(스티커, 크레파스 등)을 활용한 '재미있는 놀이'나 '시합'처럼 묘사해! 아이가 즉각적으로 따라 할 수 있는 구체적 행동 가이드를 자연스럽게 녹여내.\n"
        "9. **[바른 언어 및 금지 묘사]** 신체 부위를 묘사할 때 '이빨'이라는 표현은 절대 금지하고 반드시 '이' 또는 '치아'라고 써. 치약을 삼켜도 괜찮다는 식의 오인할 수 있는 묘사도 절대 금지해.\n"
        "10. **[사족 및 지시문 절대 금지]** 각 페이지 시작은 무조건 '[1페이지]' 등으로 시작해. '제목:', '등장인물:' 같은 대본 형식 금지. 이야기 끝에 '(전문가 팁: ...)' 같은 육아가이드나 해설을 절.대. 생성하지 마. 오직 동화 텍스트 4쪽만 출력해.\n"
        "11. **[최종 맞춤법 자체 검수]** 본문의 마침표(.)를 찍고 끝내기 직전 스스로 오탈자 검수 후 완벽히 교정된 텍스트만 출력해."
    )
    
    user_msg = (
        f"주인공 이름: {name}, 나이: {age}세, 성별: {gender}\n"
        f"성격: {child.get('personality')}\n"
        f"배경: {child.get('place')} / {child.get('time_period')}\n"
        f"분위기: {child.get('mood')}\n"
        f"문제 상황: {child.get('problem_situation')}\n"
        f"{state.get('rag_context', '')}"
    )
    
    if state.get("feedback"):
        user_msg += f"\n\n[이전 버전에 대한 피드백 - 수정 지시]\n{state['feedback']}"
        
    response = chat_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg)
    ])
    
    return {"draft_ko": response.content, "revision_count": state["revision_count"] + 1}

def review_node(state: GraphState) -> GraphState:
    draft = state["draft_ko"]
    revision_count = state["revision_count"]
    
    if '"' in draft and revision_count < 3:
        feedback = "치명적 오류: 텍스트에 쌍따옴표(\")가 발견되었습니다. 모두 작은따옴표(')로 바꾸고 다시 작성하세요."
        print("[Review] Failed: Double quotes detected.")
        return {"feedback": feedback}
    
    print("[Review] Passed")
    return {"feedback": "PASS"}

def translate_node(state: GraphState) -> GraphState:
    if state["language"].lower() == "en":
        print("[Translate] Translating to English...")
        system_prompt = (
            "You are an expert children's book translator. "
            "Translate the following Korean story into beautiful, rhythmic English suitable for a 3-5 year old. "
            "Maintain the tone, adapt rhymes, and DO NOT use double quotes (\"). Use single quotes (') only."
        )
        response = chat_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["draft_ko"])
        ])
        final_text = response.content
    else:
        final_text = state["draft_ko"]
    return {"final_text": final_text}

def format_node(state: GraphState) -> GraphState:
    print("[Format] Parsing to JSON...")
    child = state["child_info"]
    parser = PydanticOutputParser(pydantic_object=StoryFormat)
    
    system_prompt = (
        "You are a strict data formatter. Convert the story text into the exact JSON schema provided.\n"
        "1. Create an English `cover_image_prompt` that includes the character's age, gender, and appearance.\n"
        "2. Create an English `image_prompt` for EACH page based on its text.\n"
        "   - Structure: [Fixed Character Description translated to English] + [Action/Objects for the page] + [Simple background] + [, consistent character design, simple background, in watercolor children's book illustration style]\n"
        "   - If parents(mother/father) or adults appear, EXPLICITLY describe them as adults (e.g., 'a 30-year-old adult woman', 'an adult man') so they are not drawn as children or siblings.\n"
        "   - NEVER use quotes inside the image_prompt.\n"
        "3. **Generate a short Title**: Read the story text and generate a creative, short Title for the story in its original language (max 5 words). Do NOT put the whole story text into the title.\n"
        "4. **CRITICAL RULE**: Do NOT translate or change the language of the story text or title. You MUST keep the 'title' and 'text' fields in their EXACT ORIGINAL LANGUAGE (Korean or English) as provided in the Story Text.\n"
        "5. **CRITICAL RULE**: The story MUST be divided into EXACTLY 4 pages. Your JSON `content` array MUST contain EXACTLY 4 items. Do not split the story into 5, 6, or any other number of pages.\n\n"
        f"{parser.get_format_instructions()}"
    )
    
    user_msg = (
        f"Story Language: {state['language']}\n"
        f"Original Character Appearance: {child.get('appearance')}\n\n"
        f"Story Text:\n{state['final_text']}"
    )
    
    response = chat_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg)
    ])
    
    try:
        parsed = parser.parse(response.content)
        return {"final_json": parsed.model_dump_json()}
    except Exception as e:
        print(f"[Format Error] {e}")
        try:
            # Fallback to json_repair
            repaired = json_repair.loads(response.content)
            return {"final_json": json.dumps(repaired, ensure_ascii=False)}
        except Exception:
            # Ultimate fallback
            return {"final_json": response.content}

# --- Graph Assembly 1: Draft & Revise ---
def route_draft_review(state: GraphState) -> str:
    if state["feedback"] == "PASS":
        return END
    return "draft"

draft_workflow = StateGraph(GraphState)
draft_workflow.add_node("retrieve", retrieve_node)
draft_workflow.add_node("draft", draft_node)
draft_workflow.add_node("review", review_node)

draft_workflow.add_edge(START, "retrieve")
draft_workflow.add_edge("retrieve", "draft")
draft_workflow.add_edge("draft", "review")
draft_workflow.add_conditional_edges("review", route_draft_review)

draft_app = draft_workflow.compile()

# --- Graph Assembly 2: Finalize ---
finalize_workflow = StateGraph(GraphState)
finalize_workflow.add_node("translate", translate_node)
finalize_workflow.add_node("format", format_node)

finalize_workflow.add_edge(START, "translate")
finalize_workflow.add_edge("translate", "format")
finalize_workflow.add_edge("format", END)

finalize_app = finalize_workflow.compile()

# =========================================================================
# 3. 메인 인터페이스 함수 (V2)
# =========================================================================

def build_initial_state(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str) -> dict:
    child_info = {
        "name": child.name,
        "age": datetime.now().year - child.birth_year,
        "gender": child.gender,
        "appearance": appearance,
        "personality": personality,
        "place": place,
        "time_period": time_period,
        "mood": mood,
        "problem_situation": problem_situation
    }
    return {
        "child_info": child_info,
        "language": language,
        "feedback": None,
        "revision_count": 0,
        "guide_text": ""
    }

def generate_draft_text(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str = "ko") -> tuple[str, str]:
    """초안 텍스트 생성"""
    if not UPSTAGE_API_KEY:
        return f"가짜 텍스트 초안입니다. (API KEY 필요)\n\n문제 상황: {problem_situation}", "가짜 지침입니다."
        
    initial_state = build_initial_state(child, appearance, personality, place, time_period, mood, problem_situation, language)
    print(f"Starting Draft Agent for {child.name}...")
    result = draft_app.invoke(initial_state)
    return result["draft_ko"], result.get("guide_text", "")

def revise_draft_text(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str, feedback: str) -> tuple[str, str]:
    """피드백 기반 텍스트 수정"""
    if not UPSTAGE_API_KEY:
        return f"피드백이 반영된 가짜 텍스트입니다: {feedback}", "가짜 지침입니다."
        
    initial_state = build_initial_state(child, appearance, personality, place, time_period, mood, problem_situation, language)
    initial_state["feedback"] = feedback  # 피드백 주입
    print(f"Starting Revise Agent for {child.name} with feedback: {feedback}...")
    result = draft_app.invoke(initial_state)
    return result["draft_ko"], result.get("guide_text", "")

def finalize_story_json(child: Any, appearance: str, language: str, final_text: str) -> dict:
    """텍스트 확정 후 영문 번역 및 이미지 프롬프트 추출 (포맷팅)"""
    if not UPSTAGE_API_KEY:
        return {
            "title": "가짜 동화 완성",
            "cover_image_prompt": "Fake cover art",
            "content_json": "[]"
        }
    
    # finalize 에서는 child_info 중 외형 정보만 주로 필요함
    child_info = {
        "name": child.name,
        "appearance": appearance
    }
    
    initial_state = {
        "child_info": child_info,
        "language": language,
        "draft_ko": final_text
    }
    
    print("Starting Finalize Agent (Translate & Format)...")
    result = finalize_app.invoke(initial_state)
    
    final_json_str = result.get("final_json", "{}")
    try:
        parsed_obj = json.loads(final_json_str)
        return {
            "title": parsed_obj.get("title", f"{child.name}의 이야기"),
            "cover_image_prompt": parsed_obj.get("cover_image_prompt", ""),
            "content_json": json.dumps(parsed_obj.get("content", []), ensure_ascii=False)
        }
    except Exception:
        return {
            "title": "Parsing Error",
            "cover_image_prompt": "",
            "content_json": "[]"
        }

# =========================================================================
# 4. 레거시 메인 인터페이스 함수 (V1 원샷 API 용도)
# =========================================================================

def route_review(state: GraphState) -> str:
    if state["feedback"] == "PASS":
        return "translate"
    return "draft"

legacy_workflow = StateGraph(GraphState)
legacy_workflow.add_node("retrieve", retrieve_node)
legacy_workflow.add_node("draft", draft_node)
legacy_workflow.add_node("review", review_node)
legacy_workflow.add_node("translate", translate_node)
legacy_workflow.add_node("format", format_node)

legacy_workflow.add_edge(START, "retrieve")
legacy_workflow.add_edge("retrieve", "draft")
legacy_workflow.add_edge("draft", "review")
legacy_workflow.add_conditional_edges("review", route_review, {"draft": "draft", "translate": "translate"})
legacy_workflow.add_edge("translate", "format")
legacy_workflow.add_edge("format", END)

fairy_tale_app_legacy = legacy_workflow.compile()

def generate_fairy_tale_with_rag(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str = "ko") -> dict:
    """기존 V1 원샷 API를 위한 레거시 호환 함수"""
    if not UPSTAGE_API_KEY:
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (RAG 모드)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False),
            "cover_image_prompt": "A beautiful storybook cover art"
        }

    initial_state = build_initial_state(child, appearance, personality, place, time_period, mood, problem_situation, language)
    
    try:
        print(f"Starting Legacy Multi-Agent generation for {child.name} (Lang: {language})...")
        result = fairy_tale_app_legacy.invoke(initial_state)
        
        final_json_str = result.get("final_json", "{}")
        parsed_obj = json.loads(final_json_str)
        
        title = parsed_obj.get("title", f"{child.name}의 모험")
        cover_prompt = parsed_obj.get("cover_image_prompt", "A beautiful storybook cover art")
        content_array = parsed_obj.get("content", [])
        
        return {
            "title": title,
            "cover_image_prompt": cover_prompt,
            "content_json": json.dumps(content_array, ensure_ascii=False)
        }
    except Exception as e:
        print(f"Agentic Workflow Error: {e}")
        return {
            "title": f"{child.name}의 모험 (생성 실패)",
            "cover_image_prompt": "A beautiful storybook cover art",
            "content_json": json.dumps([{"page": 1, "text": "동화를 생성하는 중 오류가 발생했습니다."}], ensure_ascii=False)
        }