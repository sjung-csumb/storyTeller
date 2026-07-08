# app/agents/subgraphs/info_extractor.py
from pyexpat.errors import messages
from urllib import response

from app.agents import state
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage

from app.agents.state import InfoExtractAgentState
from app.agents.tools import search_medical_qa, solar_chat
from app.agents.utils import clean_and_parse_json, get_current_time_str
from app.core.logger import log_agent_step
# 1. 정보 추출기(Extractor) 프롬프트
# - 역할: 사용자의 질문에 답변하기 위해 내부 의료 지식 베이스(DB)를 검색합니다.
# - 핵심 행동:
# - search_medical_qa 도구를 사용하여 정보 수집
# - 정보가 충분하면 수집을 멈추고 검증 단계(Verifier)로 넘김
instruction_info_extract = """
You are the 'MedicalInfoExtractor'. Your goal is to gather medical context for the
user's query from our internal Korean-language medical knowledge base.
# Workflow
1. Internal Search: Use `search_medical_qa(query)` to find relevant information
from our knowledge base.
2. Review: Look at the results from the tool and decide if you need more search or
if you have enough raw information.
3. Finish: When you have gathered enough raw information, stop and let the
'MedicalInfoVerifier' evaluate it.
"""
# 2. 정보 검증기(Verifier) 프롬프트
# - 역할: 내부 검색으로 수집된 정보가 질문에 답변하기에 적합한지 평가합니다.
# - 평가 기준:
# - 도메인 체크: 의학/건강 관련 질문인가? (아니라면 'out_of_domain')
# - 충분성 체크: 수집된 정보로 답변이 가능한가? (가능하면 'success', 부족하면'insufficient')
# - 출력: 반드시 JSON 포맷이어야 합니다.
instruction_info_verify = """
You are the 'MedicalInfoVerifier'. Your goal is to evaluate the medical
information gathered by the extractor and determine if it's sufficient to answer
the user's query.
# Input
- User's original query.
- Retrieved documents from the internal database.
# Evaluation Criteria
1. Domain Check: Is the user's query related to medical or health topics?
 - If NOT medical-related (e.g., space, cooking, sports), set "status" to
"out_of_domain".
2. Sufficiency Check: If it IS a medical query, does the information directly
address it?
- If sufficient, set "status" to "success".
 - If insufficient or missing, set "status" to "insufficient".
# Output Format
- Return strictly JSON format: `{"status": "success" | "insufficient" |
"out_of_domain", "medical_context": "...", "key_points": ["point1", "point2",
...]}`
- Do NOT output anything else.
"""

#1.2. 도구 및 모델 설정

# app/agents/subgraphs/info_extractor.py (계속)
# Info Extractor가 사용할 도구 목록
info_extract_tools = [search_medical_qa]
# Solar LLM에 도구를 바인딩하여 도구 사용 능력을 부여
llm_info_extract = solar_chat.bind_tools(info_extract_tools)

# 1.3. 정보 추출기 노드 함수 정의
# 현재 대화 상태를 분석하여 검색 도구를 호출할지, 아니면 종료할지 결정합니다.

# app/agents/subgraphs/info_extractor.py (계속)
def info_extractor(state: InfoExtractAgentState):
    messages = state["messages"]
    # 1. 직전 도구 실행 결과 로깅 (디버깅용)
    # - 만약 직전 메시지가 도구의 응답(ToolMessage)이라면, 검색된 문서의 수 등을 요약해서 로그에 남김
    if messages and isinstance(messages[-1], ToolMessage):
        last_msg = messages[-1]
        content = last_msg.content
    if "Source 1:" in content:
        sources = content.split("Source ")[1:]
        summary = {
            "count": len(sources),
            "snippets": [s.split("\n", 1)[1][:20].strip() if "\n" in s else s[:20].strip() for s in sources]
        }
        log_agent_step("MedicalInfoExtractor", "VectorDB 검색 결과 요약", summary)
    # 2. 시스템 프롬프트 주입 (최초 실행 시)
    # - 메시지 리스트 맨 앞에 시스템 메시지가 없으면 추가해줌 (시간 정보 포함)
    if not messages or not isinstance(messages[0], SystemMessage):
        current_time = get_current_time_str()
        system_content = f"현재 시각: {current_time}\n\n{instruction_info_extract}"
        messages = [SystemMessage(content=system_content)] + messages
    # 3. LLM 호출 (내부 검색 수행 또는 종료 결정)
    log_agent_step("MedicalInfoExtractor", "검색 에이전트 시작",{"input_messages_count": len(messages)})
    response = llm_info_extract.invoke(messages)

    # 4. 다중 도구 호출 방지 (안전장치)
    # 동일 도구를 여러번 호출하도록 LLM이 응답할 수 있습니다.
    # 첫 번째 호출만 유효하게 처리
    if response.tool_calls and len(response.tool_calls) > 1:
        print(
            f"\n[MedicalInfoExtractor] Multiple tool calls detected. Keeping only the first one: {response.tool_calls[0]['name']}"
        )
        response.tool_calls = response.tool_calls[:1]
    # 5. 결과 로깅
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"\n[MedicalInfoExtractor] Tool Call: {tool_call['name']}({tool_call['args']})")
        log_agent_step("MedicalInfoExtractor", "도구 호출 응답 수신", {"tool_calls": response.tool_calls})
    else:
        log_agent_step("MedicalInfoExtractor", "검색 및 추출 완료", {"content": response.content[:100] + "..." if response.content else "None"})
    # 상태 업데이트 (새로운 AI 메시지 추가)
    return {"messages": [response]}


# 1.4. 정보 검증기 노드 함수 정의
# Extractor가 수집한 정보가 답변하기에 충분한지 검증합니다.


# app/agents/subgraphs/info_extractor.py (계속)
def info_verifier(state: InfoExtractAgentState):
    messages = state["messages"]

    # 1. 검증용 시스템 프롬프트 구성
    current_time = get_current_time_str()
    system_content = f"현재 시각: {current_time}\n\n{instruction_info_verify}"
    # 기존 대화 내역 앞에 검증 지침을 추가하여 문맥 유지
    verify_messages = [SystemMessage(content=system_content)] + messages
    # 2. LLM 호출 (검증 수행)
    log_agent_step("MedicalInfoVerifier", "검증 시작")
    response = solar_chat.invoke(verify_messages)
    # 3. 결과 파싱 (JSON) 및 로깅
    parsed = clean_and_parse_json(response.content)
    if parsed:
        log_agent_step("MedicalInfoVerifier", "검증 완료", {
            "status": parsed.get("status")
        })
    else:
        log_agent_step("MedicalInfoVerifier", "검증 완료 (파싱 실패)", {"content": response.content})
    
    return {"messages": [response]}


# 1.5. 내부 검색 결과 없음 핸들러 함수 정의
# 내부 검색 결과가 아예 없을 때 실행됩니다.
# 단순히 ‘정보 없음’으로 끝내지 않고, 사용자의 질문이 의료 도메인인지 아닌지 한 번 더 확인합니다.

# app/agents/subgraphs/info_extractor.py (계속)
def no_results_handler(state: InfoExtractAgentState):
    log_agent_step("MedicalInfoExtractor", "내부 검색 결과 없음 -> 도메인 확인 시작")
    
    current_time = get_current_time_str()

    # 도메인 판단 전용 프롬프트 (가볍게 실행)
    domain_check_prompt = f"""현재 시각: {current_time}
    Evaluate if the following user query is related to medical or health topics.
    Query: {state['messages'][1].content if len(state['messages']) > 1 else ""}

    Output strictly in JSON:
    {{"status": "out_of_domain" | "insufficient"}}

    If it IS medical but no info was found, use "insufficient".
    If it is NOT medical, use "out_of_domain".
    """
    response = solar_chat.invoke(domain_check_prompt)

    # 결과 파싱 및 로깅
    parsed = clean_and_parse_json(response.content)
    if parsed:
        log_agent_step("MedicalInfoExtractor", "도구 결과 없음 - 도메인 확인 결과", {
            "status": parsed.get("status")
        })

    return {"messages": [response]}

# 1.6. 조건부 엣지 함수 정의
# 노드 실행 후 다음으로 어디로 갈지 결정하는 로직입니다.
# app/agents/subgraphs/info_extractor.py (계속)
def should_continue(state: InfoExtractAgentState):
    """
    [엣지 결정] Extractor의 실행 결과를 보고 다음 경로를 결정합니다.
    - Tools: 도구 호출이 필요하면 -> 도구 노드로 이동
    - No Results: 도구 결과가 비어있으면 -> 예외 처리 핸들러로 이동
    - Verify: 도구 호출이 없으면(답변 완료 시) -> 검증 노드로 이동
    """
    messages = state["messages"]
    last_message = messages[-1]
    # 1. 무한 루프 방지 (안전장치)
    # - 도구를 너무 많이 호출하면 강제로 검증 단계로 넘김
    tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
    if tool_call_count > 3:
        log_agent_step("MedicalInfoExtractor", "도구 호출 횟수 초과로 강제 종료")
        return "verify"
    
    # 2. 도구 호출 확인
    if last_message.tool_calls:
        log_agent_step("MedicalInfoExtractor", "도구 호출 결정", {"tools": [tc['name'] for tc in last_message.tool_calls]})
        return "tools"
    
    # 3. 검색 결과 공백 체크 (결과가 0건인 경우 감지)
    # - 최근 메시지부터 역순으로 탐색하여 가장 최신 ToolMessage를 찾음
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # 내용이 비어있거나 에러 메시지인 경우 -> 검색 실패로 간주
            if not msg.content or msg.content.strip() == "" or msg.content.startswith("Search Error"):
                return "no_results"
            break # 가장 최근 결과만 확인하면 됨
    # 4. 그 외의 경우 (답변 생성 완료) -> 검증 단계로
    return "verify"


# 1.7. 그래프 구성
# 노드와 엣지를 연결하여 워크플로우를 완성합니다.

# app/agents/subgraphs/info_extractor.py (계속)
workflow = StateGraph(InfoExtractAgentState)
# 노드 추가
workflow.add_node("info_extractor", info_extractor) # 메인 추출기
workflow.add_node("info_extract_tools", ToolNode(info_extract_tools)) # 도구 실행기 (LangGraph 내장)
workflow.add_node("info_verifier", info_verifier) # 결과 검증기
workflow.add_node("no_results_handler", no_results_handler) # 예외 처리기


# 시작점 설정
workflow.set_entry_point("info_extractor")


# 조건부 엣지 추가 (분기점)
workflow.add_conditional_edges(
    "info_extractor",
    should_continue,
    {
        "tools": "info_extract_tools", # 도구 호출 -> 도구 실행 노드
        "verify": "info_verifier", # 완료 -> 검증 노드
        "no_results": "no_results_handler" # 실패 -> 예외 처리 노드
    }
)
# 일반 엣지 추가 (순환 및 종료)
workflow.add_edge("info_extract_tools", "info_extractor") # 도구 실행 후 -> 다시 추출기로 (결과 해석)
workflow.add_edge("info_verifier", END) # 검증 완료 -> 서브 그래프 종료
workflow.add_edge("no_results_handler", END) # 예외 처리 완료 -> 서브 그래프 종료


# 그래프 컴파일 (실행 가능한 객체 생성)
info_extract_graph = workflow.compile()
