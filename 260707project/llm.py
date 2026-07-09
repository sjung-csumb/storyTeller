import os
import json
import json_repair
import asyncio
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

# =========================================================================
# 1. 레거시 함수 (유지)
# =========================================================================
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
        "너는 아동 심리 발달을 돕는 전문 동화 작가야. "
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
    
    retriever = get_retriever("data/formatted_val.jsonl")
    query = f"카테고리: {problem}\n대상 연령: {child.get('age')}세\n주인공 성격: {child.get('personality')}\n"
    few_shot_results = retriever.retrieve_few_shot(query, top_k=1)
    
    rag_context = ""
    if few_shot_results:
        rag_context = f"--- [레퍼런스 (참고용 동화 예시)] ---\n{few_shot_results[0]}\n"
        
    return {"rag_context": rag_context, "revision_count": 0}

def draft_node(state: GraphState) -> GraphState:
    child = state["child_info"]
    age = child.get("age", 4)
    gender = child.get("gender", "무관")
    name = child.get("name", "아이")
    
    if age <= 4:
        age_rule = "3~4세 유아를 타겟으로 하므로, 아주 쉬운 어휘와 짧은 문장을 사용하고 의성어/의태어를 듬뿍 넣어서 아기자기하게 작성해."
    else:
        age_rule = "5~6세 아동을 타겟으로 하므로, 조금 더 논리적인 인과관계와 성숙한 어휘를 사용하고 교훈을 담아줘."
        
    if gender == "남자":
        gender_rule = "스토리에 모험심을 자극하고 활동적인 전개(탐험, 문제 해결 등)를 살짝 섞어주면 좋아."
    elif gender == "여자":
        gender_rule = "풍부한 감수성을 자극하고 판타지적 요소(마법, 요정 등)를 살짝 섞어주면 좋아."
    else:
        gender_rule = "아이의 성향에 맞추어 전개해."
        
    system_prompt = (
        "너는 아동 심리 발달을 돕는 다정하고 창의적인 전문 구연동화 작가야. "
        "주어진 아이의 성향과 교정해야 할 문제 상황을 바탕으로 짧고 교훈적이면서 재미있는 동화를 작성해줘. "
        "**[이야기(text) 작성 규칙]**\n"
        "0. **[치명적 규칙]** 모든 텍스트 작성 시 절대로 쌍따옴표(\")를 사용하지 마! 무조건 작은따옴표(')만 사용해!\n"
        f"1. {age_rule}\n2. {gender_rule}\n"
        f"3. 대화체는 한국 부모와 아이가 실제로 쓰는 자연스러운 구어체를 사용해 (예: '우리 {name} 기분이 어때?').\n"
        "4. 상황 묘사 시 주변 사물/동물에 빗댄 직관적 비유와 의성어/의태어를 그 동화 내용에 맞게 창작해.\n"
        "5. 아이의 감정을 신체적 반응으로 묘사하고, 입에 달라붙는 짧고 리듬감 있는 문구를 반복 삽입해.\n"
        "6. 각 페이지의 텍스트는 최소 2~3문장 이상으로 풍성하게 써! 개연성 있게 감정선을 묘사해.\n"
        "7. 4페이지 동안 '문제 발생 -> 마음 알아주기 -> 깨달음 -> 교훈'의 흐름이 물 흐르듯 이어지도록 해.\n"
        "8. 만약 꿈속 모험 이야기라면 마지막에 반드시 잠에서 깨어나 교훈을 부모님께 직접 말하며 실천하는 장면을 넣어."
    )
    
    user_msg = (
        f"주인공 이름: {name}, 나이: {age}세, 성별: {gender}\n"
        f"외형: {child.get('appearance')}\n"
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
        "   - NEVER use quotes inside the image_prompt.\n"
        "3. **CRITICAL RULE**: Do NOT translate or change the language of the story text or title. You MUST keep the 'title' and 'text' fields in their EXACT ORIGINAL LANGUAGE (Korean or English) as provided in the Story Text.\n\n"
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

# --- Graph Assembly ---

def route_review(state: GraphState) -> str:
    if state["feedback"] == "PASS":
        return "translate"
    return "draft"

workflow = StateGraph(GraphState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("draft", draft_node)
workflow.add_node("review", review_node)
workflow.add_node("translate", translate_node)
workflow.add_node("format", format_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "draft")
workflow.add_edge("draft", "review")
workflow.add_conditional_edges("review", route_review, {"draft": "draft", "translate": "translate"})
workflow.add_edge("translate", "format")
workflow.add_edge("format", END)

fairy_tale_app = workflow.compile()

# =========================================================================
# 3. 메인 인터페이스 함수
# =========================================================================
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
    LangGraph Agentic Workflow를 사용하여 동화를 생성합니다.
    """
    if not UPSTAGE_API_KEY:
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (RAG 모드)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False),
            "cover_image_prompt": "A beautiful storybook cover art"
        }

    child_info = {
        "name": child.name,
        "age": child.age,
        "gender": child.gender,
        "appearance": appearance,
        "personality": personality,
        "place": place,
        "time_period": time_period,
        "mood": mood,
        "problem_situation": problem_situation
    }
    
    initial_state = {
        "child_info": child_info,
        "language": language
    }
    
    try:
        # LangGraph Workflow 동기 실행 (FastAPI 라우트가 동기이므로 app.invoke 사용)
        print(f"Starting Multi-Agent generation for {child.name} (Lang: {language})...")
        result = fairy_tale_app.invoke(initial_state)
        
        # Parse output JSON string back to dict for the API response format
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
