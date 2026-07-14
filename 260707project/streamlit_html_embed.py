# streamlit_html_embed.py
#
# index11.html(판타지 던전 테마, 3D 책장 넘김 애니메이션, 모서리 접힘 인터랙션,
# KO/EN 동화 언어 토글, 별점 만족도 등 전부 포함)을 그대로 읽어와서
# Streamlit 안에 iframe으로 "직접 주입"하는 버전입니다.
#
# 파이썬으로 하나하나 재구현하지 않고 원본 HTML/CSS/JS를 그대로 실행하기 때문에
# index11.html을 브라우저에서 직접 연 것과 100% 동일하게 보이고 동작합니다.
# (3D 책장 넘김, 모서리 호버 효과, 별점 localStorage 저장까지 전부 원본 그대로)
#
# 전제 조건: 이 파일과 같은 폴더에 index11.html이 있어야 합니다.
#
# 실행 방법:
#   pip install streamlit
#   streamlit run streamlit_html_embed.py
#
# 참고: 이렇게 원본 HTML을 그대로 iframe에 넣는 방식은 "화면"을 100% 재현하는
# 대신, 그 안의 JS는 파이썬 쪽 세션 상태(session_state)나 실제 백엔드 API와는
# 분리되어 동작합니다. 즉 index11.html 안의 동화 내용은 여전히 하드코딩된
# 샘플 텍스트이며, 실제 AI 백엔드와 연동하려면 index11.html의 JS에서
# fetch(BACKEND_URL) 호출을 추가하는 별도 작업이 필요합니다.

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="AI 동화 만들기 - 판타지 에디션",
    page_icon="📖",
    layout="wide",
)

# Streamlit 기본 여백/헤더를 최소화해서 index11.html이 화면을 최대한 꽉 채우도록
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; max-width: 100% !important; }
    #MainMenu, header, footer { visibility: hidden; height: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

HTML_PATH = Path(__file__).parent / "index11.html"

if not HTML_PATH.exists():
    st.error(f"index11.html 파일을 찾을 수 없습니다: {HTML_PATH}")
    st.info(
        "streamlit_html_embed.py 와 index11.html이 반드시 같은 폴더(예: boot 폴더)에 "
        "있어야 합니다. 파일을 옮기거나 경로를 맞춘 뒤 다시 실행해 주세요."
    )
else:
    html_content = HTML_PATH.read_text(encoding="utf-8")
    # index11.html 자체가 3D 책장 넘김 애니메이션 / 모서리 접힘 인터랙션을 포함하고 있어서
    # 화면 높이를 넉넉히 잡고, 혹시 넘칠 경우를 대비해 내부 스크롤을 허용합니다.
    components.html(html_content, height=980, scrolling=True)
