# 1.1. 프롬프트 정의
# 지식 확장기의 역할과 행동 절차를 정의합니다.

# app/agents/subgraphs/knowledge_augmentor.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from app.agents.state import InfoBuildAgentState
#from app.agents.tools import google_search, add_to_medical_qa, solar_chat
from app.agents.tools import add_to_medical_qa, solar_chat
from app.agents.utils import get_current_time_str
from app.core.logger import log_agent_step
instruction_augment = """
You are the 'MedicalKnowledgeAugmentor'. Your goal is to search Google for medical
information and add it to our knowledge base.
# Workflow
1. Search Google: Use `Google Search(query)` to find relevant medical info.
2. Add to DB: Use `add_to_medical_qa(content, metadata)` to save the found info.
3. Termination:
 - Once you have found and added SUFFICIENT information to answer the original query, you MUST stop.
 - Do NOT repeat the same search or add redundant information.
 - If you have added at least one or two high-quality pieces of information, that is usually enough.
4. Final Answer: Return strictly JSON: `{"status": "success", "info_added":
"..."}`.
"""

# 1.2. 도구 및 모델 설정

# app/agents/subgraphs/knowledge_augmentor.py (계속)
# 이 에이전트는 '검색(Google)'과 '저장(Add to DB)' 두 가지 도구를 모두 가집니다.
#augment_tools = [google_search, add_to_medical_qa]
augment_tools = [ add_to_medical_qa]
# Solar LLM에 도구 바인딩
llm_augment = solar_chat.bind_tools(augment_tools)

# 1.3. 지식 확장 노드 함수 정의
# 외부 검색을 수행하고, 유용한 정보를 DB에 저장하는 의사결정을 합니다.

# app/agents/subgraphs/knowledge_augmentor.py (계속)
def augment_agent(state: InfoBuildAgentState):
    messages = state["messages"]
    # 1. 직전 도구 실행 결과 요약 로깅
    # - 구글 검색 결과 등은 길이가 길 수 있으므로 앞부분만 잘라서 로그에 남깁니다.
    if messages and isinstance(messages[-1], ToolMessage):
        last_msg = messages[-1]
        content = last_msg.content
        # 내부 DB 검색 결과("Source 1:...")가 아닌 일반 텍스트(구글 검색 결과 등)인 경우
        if "Source 1:" not in content and len(content) > 0:
            summary = content[:20] + "..." if len(content) > 20 else content
            log_agent_step("KnowledgeAugmentor", "Google 검색 결과 요약", {"summary": summary})
    
    # 2. 시스템 프롬프트 주입 (최초 실행 시)
    if not messages or not isinstance(messages[0], SystemMessage):
        current_time = get_current_time_str()
        system_content = f"현재 시각: {current_time}\n\n{instruction_augment}"
        messages = [SystemMessage(content=system_content)] + messages

    # 3. [중요] 루프 방지 안전장치 (Circuit Breaker)
    # - "검색 -> 저장 -> 검색 -> 저장 -> ..." 이나 "검색 -> 검색 -> 저장 -> ..." 반복을 방지하기 위해 최대 3회까지만 허용
    tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
    if tool_call_count > 3:
        log_agent_step("KnowledgeAugmentor", "최대 도구 호출 횟수 도달 -> 강제 종료")
        # 강제로 성공 메시지를 반환하여 루프를 끊음
        return {"messages": [AIMessage(content='{"status": "success", "info_added": "Maximum tool calls reached"}')]}
    
    # 4. LLM 호출
    log_agent_step("KnowledgeAugmentor", "구글 검색 및 DB 추가 시작")
    response = llm_augment.invoke(messages)
    
    log_agent_step("KnowledgeAugmentor", "응답 수신", {"content": response.content,"tool_calls": response.tool_calls})
    
    return {"messages": [response]}


# 1.4. 조건부 엣지 함수 정의
# 에이전트가 도구를 쓰려고 하는지, 아니면 작업을 마쳤는지 판단합니다

# app/agents/subgraphs/knowledge_augmentor.py (계속)
def should_continue(state: InfoBuildAgentState):
    messages = state["messages"]
    last_message = messages[-1]
    # LLM이 도구 사용을 요청했으면 -> ToolNode로 이동
    if last_message.tool_calls:
        log_agent_step("KnowledgeAugmentor", "도구 사용", {"tools": [tc['name'] for tc in last_message.tool_calls]})
        return "tools"

    # 도구 사용 요청이 없으면(작업 완료 메시지 등) -> 종료
    return END


# 1.5. 그래프 구성
# app/agents/subgraphs/knowledge_augmentor.py (계속)
workflow = StateGraph(InfoBuildAgentState)

# 노드 추가
workflow.add_node("augment_agent", augment_agent)
workflow.add_node("augment_tools", ToolNode(augment_tools)) # 도구 실행 노드

# 시작점 설정
workflow.set_entry_point("augment_agent")
# 엣지 연결
# augment_agent -> (도구 사용?) -> augment_tools 또는 END
workflow.add_conditional_edges(
    "augment_agent",
    should_continue,
    {"tools": "augment_tools", END: END}
)

# 도구 실행 후에는 다시 에이전트에게 돌아와서 다음 행동(저장할지, 그만할지)을 결정하게 함
workflow.add_edge("augment_tools", "augment_agent")

# 그래프 컴파일
knowledge_augment_graph = workflow.compile()










