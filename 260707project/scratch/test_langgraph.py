import os
import sys
import json
import asyncio

# 부모 디렉토리의 모듈을 import 하기 위해 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_upstage import ChatUpstage
from langgraph.graph import StateGraph, START, END

from kb_retriever import get_retriever

# 모델 스키마 정의 (출력용)
class StoryPage(BaseModel):
    page: int
    text: str
    image_prompt: str

class StoryFormat(BaseModel):
    title: str
    pages: List[StoryPage]

# 1. State 정의
class GraphState(TypedDict):
    # Input
    child_info: Dict[str, Any]
    language: str
    
    # Process
    rag_context: str
    draft_ko: str
    feedback: Optional[str]
    revision_count: int
    
    # Output
    final_text: str
    final_json: str

# LLM 초기화 (Upstage)
# 터미널에서 실행 시 .env 로드 필요함
from dotenv import load_dotenv
load_dotenv()
llm = ChatUpstage(model="solar-pro")

# 2. 노드 (Nodes) 정의

def retrieve_node(state: GraphState) -> GraphState:
    """RAG 검색을 수행하여 배경지식을 State에 저장"""
    child = state["child_info"]
    problem = child.get("problem_situation", "")
    
    retriever = get_retriever()
    query = f"아동 특징: 나이 {child.get('age')}세, {child.get('gender')}. 성격: {child.get('personality')}. 상황: {problem}"
    few_shot_results = retriever.retrieve_few_shot(query, top_k=1)
    
    rag_context = ""
    if few_shot_results:
        rag_context = f"--- [레퍼런스 (참고용 동화 예시)] ---\n{few_shot_results[0]}\n"
        
    print(f"[Node] Retrieve completed. Context length: {len(rag_context)}")
    
    return {"rag_context": rag_context, "revision_count": 0}


def draft_node(state: GraphState) -> GraphState:
    """한국어로 동화 초안을 작성 (텍스트만 생성)"""
    child = state["child_info"]
    context = state.get("rag_context", "")
    feedback = state.get("feedback", "")
    
    system_prompt = (
        "당신은 3~5세 유아를 위한 최고의 한국어 그림책 작가입니다.\n"
        "다음 RAG 지침과 아이 정보를 바탕으로 5페이지 분량의 동화를 작성하세요.\n"
        "각 페이지의 내용만 텍스트로 쭉 적어주세요. JSON 형식을 생각하지 마세요.\n"
        "반드시 '쌍따옴표(\")' 대신 '작은따옴표('')'만 사용하세요.\n"
        f"{context}"
    )
    
    user_msg = f"아이 이름: {child.get('name')}, 나이: {child.get('age')}, 상황: {child.get('problem_situation')}\n"
    if feedback:
        user_msg += f"\n[이전 버전에 대한 피드백 - 이를 반영하여 다시 쓰세요]\n{feedback}"
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg)
    ])
    
    draft = response.content
    print(f"[Node] Draft generated (Revision: {state['revision_count']})")
    return {"draft_ko": draft, "revision_count": state["revision_count"] + 1}


def review_node(state: GraphState) -> GraphState:
    """생성된 초안이 규칙(쌍따옴표 금지 등)을 지켰는지 자체 평가"""
    draft = state["draft_ko"]
    revision_count = state["revision_count"]
    
    # 단순 룰 검사: 쌍따옴표가 있는지?
    if '"' in draft and revision_count < 3:
        feedback = "치명적인 오류: 텍스트에 쌍따옴표(\")가 포함되어 있습니다. 모두 작은따옴표(')로 바꾸세요."
        print("[Node] Review failed. Found double quotes. Requesting revision.")
        return {"feedback": feedback}
    
    print("[Node] Review passed!")
    return {"feedback": "PASS"}


def translate_node(state: GraphState) -> GraphState:
    """언어가 'en'일 경우 번역, 'ko'면 그대로 패스"""
    if state["language"].lower() == "en":
        print("[Node] Translating to English...")
        system_prompt = (
            "You are an expert children's book translator. "
            "Translate the following Korean story into beautiful, rhythmic English suitable for a 3-5 year old. "
            "Maintain the tone, but adapt the rhymes and expressions to fit Western storytelling conventions. "
            "DO NOT use double quotes (\"). Use single quotes (') only."
        )
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["draft_ko"])
        ])
        final_text = response.content
    else:
        print("[Node] Keeping original Korean.")
        final_text = state["draft_ko"]
        
    return {"final_text": final_text}


def format_node(state: GraphState) -> GraphState:
    """최종 텍스트를 읽고 JSON(StoryFormat) 형태로 파싱"""
    print("[Node] Formatting to JSON schema...")
    from langchain_core.output_parsers import PydanticOutputParser
    
    parser = PydanticOutputParser(pydantic_object=StoryFormat)
    format_instructions = parser.get_format_instructions()
    
    system_prompt = (
        "You are a strict data formatter. Convert the following story text into the exact JSON schema provided.\n"
        "Generate creative `image_prompt` in English for each page based on the text.\n"
        f"{format_instructions}"
    )
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["final_text"])
    ])
    
    try:
        # Pydantic 객체로 파싱 후 JSON 문자열로 변환
        parsed = parser.parse(response.content)
        json_str = parsed.model_dump_json()
        print("[Node] Formatting successful!")
        return {"final_json": json_str}
    except Exception as e:
        print(f"[Node] Formatting error: {e}")
        # 실패 시 raw content 반환 (실제로는 에러 핸들링 루프 필요)
        return {"final_json": response.content}


# 3. Graph 조립 (Edges & Routing)

def route_review(state: GraphState) -> str:
    """Review 결과를 보고 루프를 돌지 진행할지 결정"""
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

# 조건부 라우팅 (리뷰 통과 여부에 따라)
workflow.add_conditional_edges(
    "review",
    route_review,
    {
        "draft": "draft",       # 실패 시 다시 draft로
        "translate": "translate" # 성공 시 번역으로
    }
)

workflow.add_edge("translate", "format")
workflow.add_edge("format", END)

# 컴파일
app = workflow.compile()


# 4. 테스트 실행
async def main():
    test_child = {
        "name": "나영",
        "age": 3,
        "gender": "여아",
        "appearance": "양갈래 머리, 핑크색 드레스",
        "personality": "말량광이",
        "place": "궁전",
        "time_period": "밤",
        "mood": "구두를 잃어버림",
        "problem_situation": "물건을 소중히 하지 못함"
    }
    
    initial_state = {
        "child_info": test_child,
        "language": "en" # 영어 테스트
    }
    
    print("=== Starting LangGraph Agentic Workflow ===")
    result = app.invoke(initial_state)
    
    print("\n=== FINAL OUTPUT JSON ===")
    print(result.get("final_json"))

if __name__ == "__main__":
    asyncio.run(main())
