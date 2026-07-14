# app/service/agents/knowledge_augmentor_service.py
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from app.agents.subgraphs.knowledge_augmentor import knowledge_augment_graph
class KnowledgeAugmentorService:
    def run(self, query: str, config: RunnableConfig = None, history: List[BaseMessage] = None) -> Dict[str, Any]:
        messages = []
        if history:
            messages.extend(history)

        # 에이전트에게 명확한 지시 전달
        messages.append(HumanMessage(content=f"Search and add info for: {query}"))
        sub_result = knowledge_augment_graph.invoke({"messages": messages}, config=config)
        # 결과 필터링
        history_len = len(messages)
        new_messages = [
            msg for msg in sub_result["messages"][history_len:]
            if isinstance(msg, AIMessage)
        ]
        return {
            "augment_logs": new_messages,
            "process_status": "augmented"
        }