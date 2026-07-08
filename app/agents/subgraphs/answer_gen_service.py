# 2. Service 로직 구현 (app/service/agents/answer_gen_service.py)
# 이 서비스의 핵심은 Info Extractor가 넘겨준 결과(extract_logs)를 해석하는 것입니다. Extractor가
# 찾은 정보(medical_context)를 프롬프트에 포함시켜 LLM에게 전달하거나, 질문이 도메인을
# 벗어났다는 판정(out_of_domain)을 받았다면 그에 맞는 대처를 하도록 지시합니다.


# app/service/agents/answer_gen_service.py
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from app.agents.subgraphs.answer_gen import answer_gen_graph
from app.agents.utils import clean_and_parse_json

class AnswerGenService:
    def run(self, user_query: str, extract_logs: List[BaseMessage], config: RunnableConfig = None, history: List[BaseMessage] = None) -> Dict[str, Any]:
        # 정보 추출 로그가 없으면 실패 처리
        if not extract_logs:
            return {"answer_logs": [AIMessage(content="Failed to extract info.")], "process_status": "fail"}
        
        # Extractor(Verifier)의 마지막 응답(JSON) 파싱
        last_extract_msg = extract_logs[-1]
        parsed_result = clean_and_parse_json(last_extract_msg.content)
        
        status = parsed_result.get("status") if parsed_result else "unknown"
        medical_context = parsed_result.get("medical_context", "") if parsed_result else ""
        
        # 상황에 따른 프롬프트 구성
        if status == "out_of_domain":
            # 도메인을 벗어난 경우의 전용 프롬프트
            prompt = f"""User Query: "{user_query}"\n\nTask: You are a medical AI
                    assistant. The user's query is unrelated to medical or health topics. Explain that
                    you are specialized in medical advice and cannot answer this specific non-medical
                    query, but offer to help with any health-related questions. Keep it polite and
                    professional in Korean. You should also refer to previous conversation history if
                    it's helpful to maintain context (e.g. if the user previously introduced
                    themselves)."""
        else:
            prompt = f"""User Query: "{user_query}"\n\nRetrieved Medical
                    Context:\n===\n{medical_context}\n===\nTask: Provide a medical consultation based
                    on the context. Refer to the previous conversation history if needed to maintain
                    continuity."""
        messages = []
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=prompt))
        #그래프 실행
        sub_result = answer_gen_graph.invoke({"messages": messages}, config=config)
        # 결과 필터링
        history_len = len(messages)
        new_messages = [
            msg for msg in sub_result["messages"][history_len:]
            if isinstance(msg, AIMessage)
        ]
        return {
            "answer_logs": new_messages,
            "process_status": "success"
        }