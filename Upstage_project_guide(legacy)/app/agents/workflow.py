# Step 5.5: 에이전트 오케스트레이션 (Super Graph)
# 1. 워크플로우 노드 함수 구현 (app/agents/workflow.py)
# LangGraph의 노드로 사용할 함수들을 정의합니다. 이 함수들은 앞서 만든 Service들을 호출하여 실제
# 작업을 수행하고, 그 결과를 전체 상태(MainState)에 업데이트합니다.


# app/agents/workflow.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from app.agents.state import MainState
from app.core.logger import log_agent_step
from app.agents.utils import clean_and_parse_json
# 1. Info Extractor 호출 노드
def call_info_extractor(state: MainState, config: RunnableConfig):
    log_agent_step("Workflow", "Step 1: MedicalInfoExtractor 시작 (RAG)")
    print(f"\n[Workflow] Step 1: MedicalInfoExtractor 시작 (Query: {state['user_query']})")

    # Get service from config
    info_extractor_service = config["configurable"].get("info_extractor_service")
    
    # loop_count 초기화 및 증가
    current_count = state.get("loop_count", 0) + 1
    
    # InfoExtractor 실행
    result = info_extractor_service.run(
        state["user_query"],
        state.get("augment_logs", []),
        config=config,
        history=state.get("answer_logs", [])
    )
    
    # loop_count 업데이트 포함
    result["loop_count"] = current_count
    
    # history 업데이트: 새로 추가된 extract_logs를 로그에 반영
    if "extract_logs" in result:
        last_msg = result["extract_logs"][-1].content
        parsed = clean_and_parse_json(last_msg)
        status = parsed.get("status") if parsed else "unknown"
        log_agent_step("Workflow", f"Step 1 완료 (반복: {current_count})", {"status": status})
        print(f"[Workflow] Step 1 완료. Status: {status}, Iteration: {current_count}")
    return result


# 2. Knowledge Augmentor 호출 노드
def call_knowledge_augmentor(state: MainState, config: RunnableConfig):
    log_agent_step("Workflow", "Step 2: MedicalKnowledgeAugmentor 시작 (Google Search)")
    print(f"\n[Workflow] Step 2: MedicalKnowledgeAugmentor 시작")
    
    # Get service from config
    knowledge_augmentor_service = config["configurable"].get("knowledge_augmentor_service")
    result = knowledge_augmentor_service.run(
        state["user_query"],
        config=config,
        history=state.get("answer_logs", [])
    )
    log_agent_step("Workflow", "Step 2 완료")
    print(f"[Workflow] Step 2 완료. 지식 보강됨.")
    return result

# 3. Answer Generator 호출 노드
def call_answer_gen(state: MainState, config: RunnableConfig):
    log_agent_step("Workflow", "Step 3: MedicalConsultant 시작")
    print(f"\n[Workflow] Step 3: MedicalConsultant (AnswerGen) 시작")
    # Get service from config
    answer_gen_service = config["configurable"].get("answer_gen_service")
    result = answer_gen_service.run(
        state["user_query"],
        state.get("extract_logs", []),
        config=config,
        history=state.get("answer_logs", [])
    )
    log_agent_step("Workflow", "Step 3 완료")
    if "answer_logs" in result:
        print(f"[Workflow] Step 3 완료. 답변 생성됨.")
    return result

# InfoExtractor의 결과에 따라 다음 단계가 어디인지 결정하는 조건부 로직입니다.
# ● 정보가 충분(success)하거나 도메인 밖(out_of_domain)이면, 답변 생성(answer_gen)으로 이동
# ● 정보가 부족(insufficient)하면, 구글 검색(augment)으로 이동
#   ● 단, 무한 루프 방지를 위해 최대 2회까지만 반복하도록 제한

# app/agents/workflow.py (계속)
def check_extract_status(state: MainState):
    if not state.get("extract_logs"): return "augment"
    last_msg = state["extract_logs"][-1].content
    parsed = clean_and_parse_json(last_msg)
    status = parsed.get("status") if parsed else "unknown"
    loop_count = state.get("loop_count", 1)
    
    # 1. 도메인을 벗어나는 경우 -> 즉시 답변 생성으로 이동 (안내 메시지 목적)
    if status == "out_of_domain":
        log_agent_step("Workflow", "도메인 외 질문 판단 -> 답변 생성 이동 (안내 메시지)")
        return "continue"
    
    # 2. "success"이면 정보를 충분히 찾은 것이므로 답변 생성으로 이동
    if status == "success":
        return "continue"
    
    # 3. 반복 횟수 체크 (최대 2회)
    if loop_count >= 2:
        log_agent_step("Workflow", f"최대 반복 횟수({loop_count}) 도달 -> 답변 생성 이동", {"reason": "Iteration limit reached"})
        return "continue"
    
    # 4. "insufficient"이거나 파싱 실패 시 구글 검색(augment)으로 이동
    log_agent_step("Workflow", "내부 지식 부족 판단 -> Google 검색 이동", {
        "reason": parsed.get("reason") if parsed else "parse error",
        "iteration": loop_count
    })
    return "augment"

def router_node(state: MainState):
    return "medical"

# 3. Super Graph 조립 및 컴파일 (app/agents/workflow.py)
# 정의한 노드들과 흐름 제어 로직을 연결하여 최종 그래프를 완성합니다. 이때 MemorySaver를
# 체크포인터로 등록하여, 에이전트가 대화의 문맥(Context)을 기억할 수 있게 합니다.

# app/agents/workflow.py (계속)
super_workflow = StateGraph(MainState)

# 노드 등록
super_workflow.add_node("info_extract_agent_workflow", call_info_extractor)
super_workflow.add_node("knowledge_augment_workflow", call_knowledge_augmentor)
super_workflow.add_node("answer_gen_agent_workflow", call_answer_gen)

# 시작점 설정
super_workflow.set_conditional_entry_point(
    router_node,
    {
        "medical": "info_extract_agent_workflow"
    }
)
# 조건부 엣지 (Extractor 결과에 따른 분기)
super_workflow.add_conditional_edges(
    "info_extract_agent_workflow",
    check_extract_status,
    {
        "continue": "answer_gen_agent_workflow",
        "augment": "knowledge_augment_workflow"
    }
)
# 순환 구조 (Augment 후 다시 Extractor로 돌아가서 재검색)
super_workflow.add_edge("knowledge_augment_workflow",
"info_extract_agent_workflow")
super_workflow.add_edge("answer_gen_agent_workflow", END)

# 메모리 기반 체크포인터 추가 (대화 기록 보존용)
memory = MemorySaver()
super_graph = super_workflow.compile(checkpointer=memory)