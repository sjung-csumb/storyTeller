# app/agents/subgraphs/answer_gen.py
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage
from app.agents.state import AnswerGenAgentState
from app.agents.tools import solar_chat
from app.agents.utils import get_current_time_str
from app.core.logger import log_agent_step
# 1. 역할 부여 (프롬프트)
instruction_answer_gen = """
You are an expert Medical Consultant.
Your goal is to provide a helpful, accurate, and empathetic medical consultation
based on the provided context.
# Guidelines:
1. Tone: Empathetic, professional, and clear.
2. Language: Korean.
3. Constraint: Do NOT provide a definitive diagnosis. Always include a disclaimer
that this is for informational purposes and the user should consult a real doctor.
4. Context: Use the provided medical QA context to support your advice.
5. Out of Domain: If the user's query is not related to medical or health topics
(check the verification result in context), politely inform them that you can only
provide medical consultations.
"""
# 2. 노드 함수 정의
def answer_gen_agent(state: AnswerGenAgentState):
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        current_time = get_current_time_str()
        system_content = f"현재 시각: {current_time}\n\n{instruction_answer_gen}"
        messages = [SystemMessage(content=system_content)] + messages
    log_agent_step("MedicalConsultant", "답변 생성 시작")
    response = solar_chat.invoke(messages)
    log_agent_step("MedicalConsultant", "답변 생성 완료", {"answer": response.content})
    return {"messages": [response]}

# 3. 그래프 구성
workflow = StateGraph(AnswerGenAgentState)
workflow.add_node("answer_gen_agent", answer_gen_agent)
workflow.set_entry_point("answer_gen_agent")
workflow.add_edge("answer_gen_agent", END)
answer_gen_graph = workflow.compile()

