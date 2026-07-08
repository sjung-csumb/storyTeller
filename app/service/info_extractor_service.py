# app/service/agents/info_extractor_service.py
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from app.agents.subgraphs.info_extractor import info_extract_graph
class InfoExtractorService:
    def run(self, user_query: str, build_logs: List[BaseMessage] = None, config:RunnableConfig = None, history: List[BaseMessage] = None) -> Dict[str, Any]:

        # 이전 컨텍스트와 함께 질문 구성
        handoff_msg = f"Original User Query: \"{user_query}\"\n\nPlease search the internal database first. Refer to the previous conversation history if it helps to understand the context of the user's query."

        if build_logs:
            handoff_msg += f"\nPrevious context: {build_logs[-1].content}"
        messages = []
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=handoff_msg))
        # 그래프 실행
        sub_result = info_extract_graph.invoke({"messages": messages},config=config)
        # 결과 필터링 (새로 생성된 AI 메시지만 추출)
        history_len = len(messages)
        new_messages = [
            msg for msg in sub_result["messages"][history_len:]
            if isinstance(msg, AIMessage)
        ]
        return {
            "extract_logs": new_messages,
            "process_status": "success"
        }