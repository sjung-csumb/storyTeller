# infra/frontend/ui.py
import streamlit as st
import json
import httpx
import uuid
import os

# 백엔드 API URL 설정
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
# 페이지 기본 설정
st.set_page_config(
    page_title="나만의 동화 제작 사이트",
    page_icon="🏥",
    layout="wide"
)

# 2. 기억 저장소: Session State (infra/frontend/ui.py)
# Streamlit은 새로고침(Rerun) 될 때마다 변수들이 초기화됩니다.
# 대화 내용을 기억하려면 특별한 저장소가 필요한데, 그것이 바로 st.session_state입니다.
# ● st.session_state:
# ● 브라우저 탭이 켜져 있는 동안 계속 유지되는 전역 변수 저장소입니다.
# ● session_id:
# ● 백엔드(LangGraph)도 사용자를 구분해야 하므로, 고유한 ID를 생성해 저장해 둡니다.
# ● 이 session id에 따라 히스토리를 저장하고, 다음의 대화에 이전 대화의 내용을
# Context로 활용하게 됩니다.
# ● messages:
# ● 주고받은 대화 내용을 [{"role": "user", "content": "안녕"}, ...] 형태로 저장합니다.

# infra/frontend/ui.py (계속)
# 세션 ID가 없으면 새로 생성 (새로고침 해도 유지됨)
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
# 대화 기록(messages) 리스트가 없으면 빈 리스트로 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []


st.title("🏥 의료 QA 에이전트 시스템")
st.markdown("이 시스템은 Upstage Solar LLM과 LangGraph를 사용하여 구축된 의료 전문 질의응답 시스템입니다. 질문을 입력하면 에이전트가 지식 베이스를 검색하고 답변을 생성합니다.") # 설명 텍스트

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 설정")
    if st.button("대화 내용 초기화"):
        # 초기화 버튼을 누르면 실행되는 코드 블록
        st.session_state.messages = [] # 대화 기록 삭제
        st.session_state.session_id = str(uuid.uuid4())




# 4. 화면 그리기: 대화 기록 표시 (infra/frontend/ui.py)
# 앱이 실행될 때마다, 이전 저장된 대화 기록(st.session_state.messages)을 꺼내서 화면에 뿌려줍니다.
# 이 과정이 없으면, 현재 응답만 나타나게 됩니다.
# ● st.chat_message(role): 채팅 메시지 모양의 말풍선을 만들어줍니다.
# ● role="user": 사용자 아이콘
# ● role="assistant": AI 로봇 아이콘
# infra/frontend/ui.py (계속)
# 저장된 메시지들을 하나씩 꺼내서 화면에 표시
for message in st.session_state.messages:
    # role에 따라 아이콘과 위치가 자동 결정됨 ("user" 또는 "assistant")
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 핵심 로직: 스트리밍 답변 생성 (infra/frontend/ui.py)
# 이 부분이 가장 까다롭지만 중요합니다. 백엔드에서 데이터가 한 글자씩 올 때마다 실시간으로 처리하는
# 함수입니다.
# ● st.status:
# ● 로딩 스피너와 로그를 보여주는 박스입니다.
# ● expanded=True면 펼쳐져 있고, 나중에 update(expanded=False)로 접을 수
# 있습니다.
# ● 사용자가 "아, 멈춘 게 아니라 내부 검색 중이구나"라고 알 수 있게 해줍니다.
# ● yield
# ● 함수가 끝나지 않고 데이터를 하나씩 건네주는(generate) 파이썬 문법입니다.
# ● Streamlit은 이 yield된 조각들을 받아 타자 치는 효과를 만듭니다.
def response_generator(prompt, session_id):
    try:
        with httpx.stream(
            "POST",
            f"{BACKEND_URL}/agent/chat/stream",
            json={
                "query": prompt,
                "session_id": session_id
            },
            timeout=None
        ) as response:
            if response.status_code != 200:
                yield f"오류가 발생했습니다 (상태 코드: {response.status_code})"
                return
        
        # 접이식 상태창 생성 ("에이전트가 분석 중입니다...")
        status = st.status("에이전트가 분석 중입니다...", expanded=True)
        is_answering = False
        for line in response.iter_lines():
            if line.startswith("data: "):
                data_str = line[len("data: "):].strip()
                
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                    if "error" in event:
                        yield f"\n\n에러 발생: {event['error']}"
                        break
                    # 로그 처리
                    # Spinner 내부(status)에 주요 단계를 표시합니다.
                    if "log" in event:
                        status.write(event['log'])
                        continue
                    # 답변 처리
                    # Spinner 외부(메인 채팅창)에 작성되어야 하므로 yield를사용합니다.
                    if "answer" in event and event["answer"]:
                        if not is_answering:
                            # 답변이 시작되면 상태창을 '완료'로 바꾸고 접어버립니다.
                            status.update(label="분석 완료", state="complete", expanded=False)
                            
                            is_answering = True
                        
                        # [핵심] yield: 데이터를 한 덩어리씩 밖으로 내보냅니다.
                        yield event["answer"]
                except json.JSONDecodeError:
                    continue
        # 루프가 끝날 때까지 answer가 없었다면 status 강제 종료
        if not is_answering:
            status.update(label="작업 완료", state="complete", expanded=False)
    except Exception as e:
        yield f"연결 오류: {str(e)}"

# 6. 사용자 입력 및 실행 (app/infra/frontend/ui.py)
# 마지막으로 사용자가 엔터를 쳤을 때의 동작입니다.
# ● st.chat_input:
# ● 하단에 고정된 입력창을 만듭니다. 사용자가 입력하고 엔터를 치면 그 내용이 prompt
# 변수에 담깁니다.
# ● st.write_stream:
# ● 제너레이터 함수(response_generator)를 실행시키고, 거기서 나오는 텍스트 조각들을
# 실시간으로 타자기 효과와 함께 화면에 뿌려줍니다. Streamlit의 가장 강력한 기능 중
# 하나입니다.
# 화면 하단에 채팅 입력창 생성
if prompt := st.chat_input("의료 관련 질문을 입력하세요."):

    # 1. 사용자 질문을 먼저 화면에 그리기
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    # 2. AI 답변 영역 그리기
    with st.chat_message("assistant"):
        # [핵심] response_generator가 yield하는 글자들을 실시간으로 화면에 씀
        full_response = st.write_stream(response_generator(prompt, st.session_state.session_id))

    # 3. 답변이 다 완성되면 저장소에 기록
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response
    })

# Footer information
st.markdown("---")
st.caption("Powered by Upstage Solar LLM & LangGraph")