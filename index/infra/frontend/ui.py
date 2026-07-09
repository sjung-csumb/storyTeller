import streamlit as st
import json
import httpx
import uuid
import os

# 백엔드 API URL 설정
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
# 페이지 기본 설정
st.set_page_config(
    page_title="의료 QA 에이전트",
    page_icon="🏥",
    layout="wide",
)