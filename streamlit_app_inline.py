# streamlit_app_inline.py
#
# index11.html의 HTML/CSS/JS 전체를 이 파이썬 파일 하나에 그대로 넣은(inline) 버전입니다.
# 외부 index11.html 파일을 따로 두지 않아도 되므로, 파일을 통째로 옮기거나 배포하기 더 간단합니다.
# 화면/동작은 index11.html을 직접 연 것과 100% 동일합니다.
#
# 실행 방법:
#   pip install streamlit
#   streamlit run streamlit_app_inline.py
#
# 나중에 백엔드와 연동하고 싶을 때:
#   아래 HTML_TEMPLATE은 일반 문자열(f-string이 아님)입니다. CSS/JS에 중괄호 { }가 매우 많아서
#   f-string으로 바꾸면 전부 {{ }}로 이스케이프해야 하는 번거로움이 생기기 때문입니다.
#   대신 이렇게 하면 됩니다.
#     1) HTML_TEMPLATE 안에 __BACKEND_URL__ 같은 자리표시자(placeholder)를 심어두고,
#        HTML_TEMPLATE.replace("__BACKEND_URL__", BACKEND_URL) 으로 실행 시점에 값을 주입합니다.
#     2) <script> 안의 initBookData() 함수를 하드코딩된 샘플 텍스트 대신
#        fetch(`${BACKEND_URL}/generate`, {...}) 호출로 실제 동화를 받아오도록 바꿉니다.
#   이 파일 하나 안에서 파이썬(백엔드 호출 URL 등)과 HTML(화면)을 같이 관리할 수 있어
#   오히려 파일이 여러 개로 나뉘어 있을 때보다 관리가 편해질 수 있습니다.

# ----------------------------------------------------------------------------
# 별점 만족도 파일 저장 (책 안의 별점을 그대로 사용, 이름/언어 포함)
# ----------------------------------------------------------------------------
# 아래 HTML_TEMPLATE 안의 별점(★)은 iframe(components.html) 안에서 동작하는 순수 JS라서,
# 클릭하면 "브라우저의 localStorage"에 heroName/language/rating이 함께 저장됩니다.
# iframe은 보안상 격리되어 있어 파이썬이 그 값을 직접 받을 수 없기 때문에,
# streamlit-javascript로 localStorage 값을 읽어오고, streamlit-autorefresh로
# 몇 초마다 자동으로 다시 확인해서 값이 바뀌면 satisfaction_ratings.json에 저장합니다.
# (iframe 밖에 별도의 별점 UI를 두지 않고, 책 안의 별점만 사용합니다)
#
# 추가로 필요한 패키지:
#   pip install streamlit streamlit-javascript streamlit-autorefresh

import base64
import json
import os
import warnings
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# st.components.v1.html Deprecation Warning 터미널 도배 방지
warnings.filterwarnings("ignore", message=".*replace.*st.components.v1.html.*with.*st.iframe.*")
warnings.filterwarnings("ignore", message=".*st.components.v1.html.*will be removed.*")

try:
    from streamlit_javascript import st_javascript
    from streamlit_autorefresh import st_autorefresh
    _SYNC_AVAILABLE = True
except ImportError:
    _SYNC_AVAILABLE = False

RATINGS_FILE = Path(__file__).parent / "satisfaction_ratings.json"
STATIC_DIR = Path(__file__).parent / "static"


def load_image_data_uri(filename, mime="image/jpeg"):
    """static/ 폴더의 배경 이미지를 base64 data URI로 읽어옵니다.
    파일이 없으면 빈 문자열을 돌려줘서(그라데이션만 남고) 앱이 죽지 않게 합니다."""
    path = STATIC_DIR / filename
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

st.set_page_config(
    page_title="AI 동화 만들기 - 판타지 에디션",
    page_icon="📖",
    layout="wide",
)

if "last_synced_rating_raw" not in st.session_state:
    st.session_state.last_synced_rating_raw = None


def save_rating_record(record):
    try:
        data = []
        if RATINGS_FILE.exists():
            data = json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
        data.append(record)
        RATINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        st.warning(f"만족도 저장 중 오류가 발생했어요: {e}")


def already_saved(rated_at_browser):
    """파일에 저장된 마지막 기록이 이번 별점 이벤트(브라우저에서 저장된 시각 기준)와
    같은지 확인합니다. st.session_state는 세션이 재연결/새로고침되면 초기화되지만,
    파일은 항상 그대로 남아있으므로 이 방식이 훨씬 안전합니다."""
    if not rated_at_browser:
        return False
    try:
        if RATINGS_FILE.exists():
            data = json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
            if data:
                last = data[-1]
                return last.get("rated_at_browser") == rated_at_browser
    except Exception:
        pass
    return False

# Streamlit 기본 여백/헤더를 최소화해서 아래 HTML이 화면을 최대한 꽉 채우도록
st.markdown(
    """
    <style>
    .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; margin-top: 0rem !important; max-width: 100% !important; }
    #MainMenu, header, footer { visibility: hidden; height: 0; display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# index11.html 전체 (HTML + CSS + JS) - 그대로 문자열로 포함
# ----------------------------------------------------------------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 동화 만들기 - 판타지 에디션</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @font-face {
            font-family: 'OngleipParkDahyeon';
            src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/2411-3@1.0/Ownglyph_ParkDaHyun.woff2') format('woff2');
            font-weight: normal;
            font-display: swap;
        }

        body {
            font-family: 'OngleipParkDahyeon', sans-serif;
            transition: background 1.5s ease-in-out;
        }

        .fade-in {
            animation: fadeIn 0.5s ease-in-out forwards;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .hidden-stage {
            display: none !important;
        }

        .float-cloud {
            animation: floatCloud 3s ease-in-out infinite;
        }
        @keyframes floatCloud {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
            100% { transform: translateY(0px); }
        }

        /* --- 판타지 던전 테마 배경 --- */
        .bg-dungeon-theme {
            background-color: #050402 !important;
            background-image: radial-gradient(circle at 50% 50%, #3e2b14 0%, #171109 45%, #050402 100%) !important;
        }

        /* --- 낡은 가죽 커버 디자인 --- */
        .page-leather {
            background-color: #3b2313;
            /* 가죽 질감을 위한 노이즈 패턴 */
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.15'/%3E%3C/svg%3E"), radial-gradient(circle at center, #4a2e1b 0%, #29160a 100%);
            box-shadow: inset 0 0 30px rgba(0,0,0,0.9), 0 15px 25px rgba(0,0,0,0.8);
        }

        /* --- 색바랜 파피루스 속지 디자인 --- */
        .page-papyrus {
            background-color: #e6d8ba;
            /* 종이 질감을 위한 미세 노이즈 패턴 */
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='paperNoise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23paperNoise)' opacity='0.08'/%3E%3C/svg%3E");
            box-shadow: inset 0 0 50px rgba(139, 90, 43, 0.25), inset 0 0 15px rgba(139, 90, 43, 0.2);
        }

        /* 중앙 책등(Spine) 그림자 효과 */
        .book-spine {
            background: linear-gradient(to right, rgba(0,0,0,0) 0%, rgba(0,0,0,0.3) 40%, rgba(0,0,0,0.6) 50%, rgba(0,0,0,0.3) 60%, rgba(0,0,0,0) 100%);
        }

        /* --- 3D 책장 넘김 및 파피루스 모서리 효과 --- */
        .preserve-3d { transform-style: preserve-3d; }
        .backface-hidden {
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
        }

        .corner-right-fold {
            border-bottom: 35px solid #cca97e; /* 파피루스 뒷면 그늘진 색 */
            border-left: 35px solid transparent;
            transition: all 0.3s ease;
            transform-origin: bottom right;
            filter: drop-shadow(-3px -3px 3px rgba(0,0,0,0.2));
        }
        .group:hover .corner-right-fold {
            border-bottom: 55px solid #b8915e;
            border-left: 55px solid transparent;
        }

        .corner-left-fold {
            border-bottom: 35px solid #cca97e;
            border-right: 35px solid transparent;
            transition: all 0.3s ease;
            transform-origin: bottom left;
            filter: drop-shadow(3px -3px 3px rgba(0,0,0,0.2));
        }
        .group:hover .corner-left-fold {
            border-bottom: 55px solid #b8915e;
            border-right: 55px solid transparent;
        }

        /* --- 언어 토글 버튼 --- */
        .lang-toggle-btn {
            transition: all 0.25s ease;
        }
        .lang-toggle-btn.active {
            background-color: #fbbf24;
            color: #1f2937;
            box-shadow: 0 2px 6px rgba(251,191,36,0.5);
        }
        .lang-toggle-btn:not(.active) {
            color: #9ca3af;
        }

        /* --- 별점 위젯 --- */
        .star-btn {
            background: none;
            border: none;
            cursor: pointer;
            line-height: 1;
            padding: 0;
        }
        .star-btn:focus {
            outline: none;
        }

        /* ================================================================
           스테이지별 모험 배경 (숲 입구 → 동굴 던전 입구 → 보물의 방)
           - 순수 CSS/SVG(data URI)/이모지로만 구성해서 외부 이미지 요청이 없습니다.
           - 입력 카드(storybook-card)는 항상 불투명하게 위에 떠 있어서,
             배경이 아무리 화려해져도 입력/안내 문구 가독성에는 영향이 없습니다.
           - goToStage()가 stage 번호에 맞춰 scene-forest/cave/vault 클래스를 바꿔줍니다.
           - 던전(로딩/책) 테마로 전환되면 전체가 자연스럽게 사라집니다.
           ================================================================ */
        .scene-backdrop {
            position: fixed;
            inset: 0;
            z-index: 0;
            overflow: hidden;
            pointer-events: none;
            transition: opacity 1.4s ease-in-out;
        }
        body.bg-dungeon-theme .scene-backdrop {
            opacity: 0;
        }

        .scene-layer {
            position: absolute;
            inset: 0;
            opacity: 0;
            transition: opacity 1.1s ease-in-out;
        }
        .scene-backdrop.scene-forest .scene-layer-forest,
        .scene-backdrop.scene-cave .scene-layer-cave,
        .scene-backdrop.scene-vault .scene-layer-vault {
            opacity: 1;
        }

        /* ---------- 1. 숲의 입구 (Stage 1) ---------- */
        .forest-sky {
            position: absolute;
            inset: 0;
            background-color: #1b2a33;
            background-size: cover;
            background-position: center 35%;
            /* 아래 url()에는 static/bg_forest.jpg가 base64 data URI로 주입됩니다 */
            background-image: url("__BG_FOREST__");
        }

        /* ---------- 2. 동굴(던전) 입구 (Stage 2) ---------- */
        .cave-bg {
            position: absolute;
            inset: 0;
            background-color: #120c22;
            background-size: cover;
            background-position: center;
            /* 아래 url()에는 static/bg_cave.jpg가 base64 data URI로 주입됩니다 */
            background-image: url("__BG_CAVE__");
        }
        .cave-mist {
            position: absolute;
            left: 0; right: 0; bottom: 0;
            height: 22%;
            background: linear-gradient(180deg, rgba(30,20,55,0) 0%, rgba(20,14,38,0.85) 100%);
        }

        /* ---------- 3. 보물의 방 (Stage 3) ---------- */
        .vault-bg {
            position: absolute;
            inset: 0;
            background-color: #0c0703;
            background-size: cover;
            background-position: center;
            /* 아래 url()에는 static/bg_vault.jpg가 base64 data URI로 주입됩니다 */
            background-image: url("__BG_VAULT__");
        }

        /* --- 동화책 표지 느낌의 메인 카드 (배경 사진이 살짝 비치는 반투명 유리 느낌) --- */
        .storybook-card {
            position: relative;
            z-index: 10;
        }
        .storybook-card::before {
            content: "";
            position: absolute;
            inset: 9px;
            border: 2px dashed rgba(217, 164, 65, 0.35);
            border-radius: 22px;
            pointer-events: none;
            transition: opacity 0.8s ease;
        }
        body.bg-dungeon-theme .storybook-card::before {
            opacity: 0;
        }
        /* stage1~3(던전 테마가 아닐 때)에만 반투명 유리 배경을 입혀서 뒤의 사진이 은은하게 비치게 합니다.
           #mainBox 아이디를 포함해 명시도를 높여서 Tailwind의 bg-white 유틸리티보다 항상 우선 적용되고,
           로딩/책 단계(던전 테마)에서는 이 규칙이 아예 적용되지 않아 기존 bg-black/40 스타일이 그대로 유지됩니다. */
        body:not(.bg-dungeon-theme) #mainBox.storybook-card {
            background-color: rgba(255, 253, 247, 0.82);
            backdrop-filter: blur(14px) saturate(1.1);
            -webkit-backdrop-filter: blur(14px) saturate(1.1);
        }

        /* --- 스테이지 2/3 카드 뒤에 가려지는 동굴 입구/전설의 서를 카드 위쪽 "창문"으로 보여줍니다 --- */
        .scene-peek {
            width: 100%;
            height: 128px;
            background-size: cover;
            border-radius: 18px;
            margin-bottom: 1.1rem;
            position: relative;
            box-shadow: 0 8px 22px rgba(0,0,0,0.35), inset 0 0 0 2px rgba(255,255,255,0.18);
        }
        .scene-peek::after {
            content: "";
            position: absolute;
            inset: 0;
            border-radius: inherit;
            background: linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(0,0,0,0.4) 100%);
        }
        .scene-peek-cave {
            background-image: url("__BG_CAVE__");
            background-position: center 30%;
            box-shadow: 0 8px 22px rgba(0,0,0,0.35), inset 0 0 0 2px rgba(147, 165, 255, 0.4);
        }
        .scene-peek-vault {
            background-image: url("__BG_VAULT__");
            background-position: center 38%;
            box-shadow: 0 8px 22px rgba(0,0,0,0.35), inset 0 0 0 2px rgba(255, 205, 110, 0.45);
        }

        /* --- 스테이지 2 (동굴) 배경에 어울리는 입력칸 --- */
        #stage2 input[type="text"] {
            background-color: rgba(24, 20, 45, 0.55);
            color: #e9e9ff;
            border-color: rgba(147, 165, 255, 0.4);
        }
        #stage2 input[type="text"]::placeholder {
            color: rgba(210, 216, 255, 0.55);
        }
        #stage2 input[type="text"]:focus {
            background-color: rgba(24, 20, 45, 0.72);
            border-color: #93a5ff;
        }

        /* --- 스테이지 3 (보물의 방) 배경에 어울리는 입력칸 --- */
        #stage3 textarea {
            background-color: rgba(58, 38, 16, 0.1);
            color: #4a2e15;
            border-color: rgba(190, 140, 60, 0.45);
        }
        #stage3 textarea::placeholder {
            color: rgba(120, 90, 50, 0.6);
        }
        #stage3 textarea:focus {
            background-color: rgba(255, 250, 235, 0.85);
            border-color: #b8860b;
        }

        /* --- 입력 항목 아이콘 뱃지 --- */
        .field-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-right: 4px;
        }

        /* --- 진행 단계 점(dot) 크기/발광 강조 --- */
        .stage-dot {
            transition: all 0.4s ease;
        }
        .stage-dot.stage-dot-active {
            box-shadow: 0 0 10px 2px rgba(251, 191, 36, 0.65);
            transform: scale(1.15);
        }

        /* --- SMILE 로고 (모든 스테이지에 고정, 어두운 배경 위에서도 흰색 글로우로 잘 보이게) --- */
        .logo-smile-img {
            height: 86px;
            width: auto;
            display: block;
            filter:
                drop-shadow(0 0 3px rgba(255,255,255,0.85))
                drop-shadow(0 0 8px rgba(255,255,255,0.55))
                drop-shadow(0 0 16px rgba(255,255,255,0.3));
        }
    </style>
</head>
<body class="bg-stone-100 text-gray-800 min-h-screen flex flex-col items-center justify-center p-6 transition-colors duration-1000">

    <!-- 스테이지별 모험 배경 (숲 입구 → 동굴 던전 입구 → 보물의 방). 순수 장식용이라 클릭/폼 로직에는 영향이 없고,
         goToStage()가 stage 번호에 맞춰 scene-forest/scene-cave/scene-vault 클래스를 바꿔줍니다. -->
    <div id="sceneBackdrop" class="scene-backdrop scene-forest" aria-hidden="true">

        <!-- 1. 숲의 입구 -->
        <div class="scene-layer scene-layer-forest">
            <div class="forest-sky"></div>
        </div>

        <!-- 2. 동굴(던전) 입구 -->
        <div class="scene-layer scene-layer-cave">
            <div class="cave-bg"></div>
            <div class="cave-mist"></div>
        </div>

        <!-- 3. 보물의 방 (전설의 동화책을 얻는 곳) -->
        <div class="scene-layer scene-layer-vault">
            <div class="vault-bg"></div>
        </div>
    </div>

    <!-- 내가 만든 동화 히스토리 (햄버거 메뉴) -->
    <button type="button" id="historyMenuBtn" onclick="openHistoryDrawer()" title="내가 만든 동화 보기"
        class="fixed top-6 left-10 z-40 w-11 h-11 rounded-full bg-white/85 hover:bg-white shadow-md border border-stone-200 flex items-center justify-center text-xl text-stone-700 transition-all hover:scale-105 backdrop-blur-sm">
        ☰
    </button>

    <div id="historyOverlay" onclick="closeHistoryDrawer()" class="fixed inset-0 bg-black/50 z-40 hidden"></div>

    <div id="historyDrawer" class="fixed top-0 left-0 h-full w-80 max-w-[85vw] bg-stone-50 shadow-2xl z-50 -translate-x-full transition-transform duration-300 ease-in-out flex flex-col">
        <div class="flex items-center justify-between py-5 pr-5 pl-10 border-b border-stone-200">
            <h3 class="text-xl font-bold text-stone-800">📚 내가 만든 동화</h3>
            <button type="button" onclick="closeHistoryDrawer()" class="text-2xl leading-none text-stone-400 hover:text-stone-700">&times;</button>
        </div>
        <div id="historyList" class="flex-1 overflow-y-auto py-4 pr-4 pl-10 space-y-3"></div>
    </div>

    <!-- SMILE 로고 (모든 스테이지 + 동화 생성 이후에도 항상 떠 있고, 클릭하면 처음으로 리셋) -->
    <button type="button" id="logoResetBtn" onclick="location.reload()" title="처음으로 돌아가기"
        class="fixed top-6 right-10 z-40 bg-transparent border-none p-0 cursor-pointer transition-transform hover:scale-105">
        <img src="__SMILE_LOGO__" alt="SMILE 로고" class="logo-smile-img">
    </button>

    <div id="mainBox" class="storybook-card w-full max-w-xl bg-white rounded-3xl p-10 shadow-2xl border border-stone-200 relative overflow-hidden transition-all duration-1000 ease-in-out">
        <!-- 1. stage1 주인공 이름 -->
        <div id="stage1" class="fade-in">
            <div class="text-center mb-8">
                <div class="flex justify-center items-center gap-2 mb-2">
                    <span class="stage-dot stage-dot-active w-2.5 h-2.5 rounded-full bg-amber-400"></span>
                    <span class="stage-dot w-2.5 h-2.5 rounded-full bg-gray-200"></span>
                    <span class="stage-dot w-2.5 h-2.5 rounded-full bg-gray-200"></span>
                </div>
                <span class="text-xs font-semibold tracking-wider text-amber-500 uppercase">STAGE 1 / 3</span>
                <h1 class="text-3xl font-bold mt-1 text-gray-800">📖 SMILE</h1>
                <p class="text-xl font-bold mt-1 text-gray-600">행동 교정 동화 생성 서비스</p>
            </div>

            <form class="space-y-6" onsubmit="event.preventDefault(); goToStage(2);">
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2"><span class="field-icon">🧑</span>주인공 이름</label>
                    <input type="text" id="heroNameInput" placeholder="예: 김사과" class="w-full bg-stone-50 border border-stone-200 rounded-[20px] px-4 py-3 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>

                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2"><span class="field-icon">🎂</span>출생연도</label>
                    <input type="text" id="birthYearInput" inputmode="numeric" maxlength="4" placeholder="예: 2026" class="w-full bg-stone-50 border border-stone-200 rounded-[20px] px-4 py-3 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>

                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2"><span class="field-icon">👫</span>성별</label>
                    <div class="flex gap-2">
                        <label class="flex-1 relative flex items-center justify-center gap-2 bg-stone-50 border border-stone-200 rounded-xl p-3 cursor-pointer hover:border-stone-300 hover:scale-[1.02] transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="gender" value="male" class="absolute opacity-0 peer">
                            <span class="text-xl">🤴</span>
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">남</span>
                        </label>
                        <label class="flex-1 relative flex items-center justify-center gap-2 bg-stone-50 border border-stone-200 rounded-xl p-3 cursor-pointer hover:border-stone-300 hover:scale-[1.02] transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="gender" value="female" class="absolute opacity-0 peer">
                            <span class="text-xl">👸</span>
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">여</span>
                        </label>
                    </div>
                </div>

                <button type="submit" class="w-full bg-amber-400 hover:bg-amber-300 text-xl text-gray-900 font-bold py-4 rounded-[20px] shadow-sm hover:shadow-md hover:scale-[1.02] active:scale-95 transition-all mt-6 flex items-center justify-center gap-2">
                    다음 단계로 이동 ➜
                </button>
            </form>
        </div>

        <div id="stage2" class="hidden-stage fade-in">
            <div class="scene-peek scene-peek-cave" aria-hidden="true"></div>
            <div class="text-center mb-8">
                <div class="flex justify-center items-center gap-2 mb-2">
                    <span class="stage-dot w-2.5 h-2.5 rounded-full bg-gray-200"></span>
                    <span class="stage-dot stage-dot-active w-2.5 h-2.5 rounded-full bg-amber-400"></span>
                    <span class="stage-dot w-2.5 h-2.5 rounded-full bg-gray-200"></span>
                </div>
                <span class="text-xs font-semibold tracking-wider text-amber-500 uppercase">STAGE 2 / 3</span>
                <h2 class="text-3xl font-bold mt-1 text-gray-800">🪄 어떤 이야기인가요?</h2>
                <p class="text-2xs text-gray-500 mt-1">주인공과 배경에 대해 더 자세히 알려주세요</p>
            </div>
            <form class="space-y-4" onsubmit="event.preventDefault(); goToStage(3);">
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-1"><span class="field-icon">👗</span>주인공의 외형</label>
                    <input type="text" id="appearanceInput" placeholder="예: 빨간 모자를 쓰고 있어요" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-1"><span class="field-icon">💫</span>주인공의 성격</label>
                    <input type="text" id="personalityInput" placeholder="예: 호기심이 많고 용감해요" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xl font-semibold text-gray-700 mb-1"><span class="field-icon">🗺️</span>장소</label>
                        <input type="text" id="placeInput" placeholder="예: 깊은 숲속" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                    </div>
                    <div>
                        <label class="block text-xl font-semibold text-gray-700 mb-1"><span class="field-icon">⏳</span>시대</label>
                        <input type="text" id="timePeriodInput" placeholder="예: 아주 먼 옛날" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                    </div>
                </div>
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-1"><span class="field-icon">🌈</span>분위기</label>
                    <input type="text" id="moodInput" placeholder="예: 신비롭고 따뜻한 느낌" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>
                <div class="flex gap-3 mt-6">
                    <button type="button" onclick="goToStage(1)" class="w-1/3 bg-stone-100 hover:bg-stone-200 text-xl text-gray-600 font-bold py-4 rounded-[20px] transition-all flex items-center justify-center">이전</button>
                    <button type="submit" class="w-2/3 bg-amber-400 hover:bg-amber-300 text-xl text-gray-900 font-bold py-4 rounded-[20px] shadow-sm hover:shadow-md hover:scale-[1.02] active:scale-95 transition-all flex items-center justify-center gap-2">다음 단계로 ➜</button>
                </div>
            </form>
        </div>

        <div id="stage3" class="hidden-stage fade-in relative">
            <div class="scene-peek scene-peek-vault" aria-hidden="true"></div>

            <!-- 언어 선택 토글 (KO/EN) -->
            <div class="absolute top-3 right-3 flex items-center gap-1 bg-stone-100 border border-stone-200 rounded-full p-1 z-10">
                <button type="button" id="langKoBtn" onclick="setStoryLanguage('ko')" class="lang-toggle-btn active px-3 py-1.5 rounded-full text-sm font-bold">KO</button>
                <button type="button" id="langEnBtn" onclick="setStoryLanguage('en')" class="lang-toggle-btn px-3 py-1.5 rounded-full text-sm font-bold">EN</button>
            </div>

            <div class="text-center mb-8">
                <div class="flex justify-center items-center gap-2 mb-2">
                    <span class="stage-dot w-2.5 h-2.5 rounded-full bg-gray-200"></span>
                    <span class="stage-dot w-2.5 h-2.5 rounded-full bg-gray-200"></span>
                    <span class="stage-dot stage-dot-active w-2.5 h-2.5 rounded-full bg-amber-400"></span>1
                </div>
                <span class="text-xs font-semibold tracking-wider text-amber-500 uppercase">STAGE 3 / 3</span>
                <h2 class="text-3xl font-bold mt-1 text-gray-800" id="stage3Title">📜 어떤 일이 생겼나요?</h2>
                <p class="text-2xs text-gray-500 mt-1" id="stage3Subtitle">주인공이 겪는 문제나 사건을 적어주세요</p>
            </div>
            <form class="space-y-6" onsubmit="event.preventDefault(); submitForm();">
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2" id="problemLabel"><span class="field-icon">📝</span>문제 상황</label>
                    <p class="text-sm text-amber-700 mb-3 bg-amber-50 p-2.5 rounded-xl border border-amber-200">💡 <b>Tip:</b> "아이가 ~해서 실망했어요"보다 <b>"아이에게 ~하는 용기를 주고 싶어요"</b>라고 적어주시면, 긍정적 행동 변화를 이끌어내는 데 훨씬 효과적입니다!</p>
                    <textarea id="problemTextarea" rows="7" placeholder="예: 소중한 장난감을 잃어버려서 슬퍼하고 있어요. 친구들과 어떻게 화해해야 할지 모르겠어요." class="w-full bg-stone-50 border border-stone-200 rounded-[20px] px-4 py-4 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors resize-none" required></textarea>
                </div>
                <div class="flex gap-3 mt-6">
                    <button type="button" onclick="goToStage(2)" class="w-1/3 bg-stone-100 hover:bg-stone-200 text-xl text-gray-600 font-bold py-4 rounded-[20px] transition-all flex items-center justify-center" id="prevBtnText">이전</button>
                    <button type="submit" class="w-2/3 bg-orange-400 hover:bg-orange-500 text-xl text-white font-bold py-4 rounded-[20px] shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-95 transition-all flex items-center justify-center gap-2" id="submitBtnText">✨ 이야기 만들기!</button>
                </div>
            </form>
        </div>

        <div id="stageLoading" class="hidden-stage text-center py-10 fade-in flex flex-col items-center justify-center">
            <div class="float-cloud w-20 h-20 bg-amber-900/40 border border-amber-600/50 text-amber-400 rounded-full flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(217,119,6,0.5)]">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-10 h-10"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15a4.5 4.5 0 0 0 4.5 4.5H18a3.75 3.75 0 0 0 1.332-7.257 3 3 0 0 0-3.758-3.848 5.25 5.25 0 0 0-10.233 2.33A4.502 4.502 0 0 0 2.25 15Z" /></svg>
            </div>
            <h2 class="text-3xl font-bold text-amber-200 mb-2 drop-shadow-md" id="loadingTitle">마법의 책을 엮는 중...</h2>
            <p class="text-lg text-amber-100/70 mb-8" id="loadingStatusText">신비로운 동화를 준비하고 있어요</p>

            <div class="w-full px-2">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-sm font-semibold text-amber-400" id="loadingPhase">주문 외우는 중...</span>
                    <span class="text-base font-bold text-amber-200" id="progressPercent">0%</span>
                </div>
                <div class="w-full h-3 bg-stone-900 rounded-full overflow-hidden border border-amber-900/50 shadow-inner">
                    <div id="progressBar" class="h-full bg-gradient-to-r from-amber-600 via-yellow-500 to-amber-300 rounded-full transition-all duration-300 ease-out shadow-[0_0_10px_rgba(252,211,77,0.8)]" style="width: 0%;"></div>
                </div>
            </div>

            <!-- 전문가 육아 지침 영역 (그림 생성 단계에서만 보임) -->
            <div id="guideTextContainer" class="hidden w-full mt-10 bg-black/40 border border-amber-700/50 rounded-2xl p-5 shadow-2xl backdrop-blur-sm text-left opacity-0 transition-opacity duration-1000">
                <h3 class="text-base font-bold text-amber-400 mb-2 flex items-center gap-2">
                    <span class="text-lg">💡</span>이 동화에 쓰인 육아 지침
                </h3>
                <p id="guideTextContent" class="text-lg text-amber-50/90 leading-relaxed whitespace-pre-wrap max-h-[140px] overflow-y-auto pr-2"></p>
            </div>
        </div>

        <div id="stageDraft" class="hidden-stage fade-in w-full">
            <div class="text-center mb-6">
                <span class="text-sm font-semibold tracking-wider text-amber-500 uppercase">이야기 초안</span>
                <h2 class="text-3xl font-bold mt-1 text-gray-800">✏️ 이야기가 이렇게 만들어졌어요</h2>
                <p class="text-sm text-gray-500 mt-1">아직 그림은 그리지 않았어요. 고치고 싶은 부분이 있으면 알려주세요.</p>
            </div>

            <div id="draftPagesContainer" class="space-y-4 max-h-[55vh] overflow-y-auto px-1 mb-4 pr-2">
                <!-- JS(renderDraftPages)로 채워짐: 페이지별 텍스트 카드. 내용이 넘치면 이 안에서만 스크롤됩니다 -->
            </div>

            <div id="feedbackLog" class="space-y-1 mb-3 text-xs text-emerald-600"></div>

            <div class="space-y-3">
                <label class="block text-lg font-semibold text-gray-700">
                    <span class="field-icon">💬</span>어떻게 고쳐드릴까요?
                    <span class="text-sm text-gray-400 font-normal">(예: 아빠도 등장시켜줘, 결말을 더 신나게 해줘)</span>
                </label>
                <textarea id="feedbackTextarea" rows="3" placeholder="수정하고 싶은 부분을 적어주세요. 없다면 비워두고 바로 그림을 그려도 돼요." class="w-full bg-stone-50 border border-stone-200 rounded-[20px] px-4 py-3 text-base text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors resize-none"></textarea>

                <div class="flex gap-3">
                    <button type="button" onclick="submitFeedback()" id="reviseBtn" class="w-1/2 bg-stone-100 hover:bg-stone-200 text-lg text-gray-700 font-bold py-4 rounded-[20px] transition-all">
                        📝 이 내용으로 다시 써줘
                    </button>
                    <button type="button" onclick="finalizeStory()" id="finalizeBtn" class="w-1/2 bg-amber-400 hover:bg-amber-300 text-lg text-gray-900 font-bold py-4 rounded-[20px] shadow-sm hover:shadow-md hover:scale-[1.02] active:scale-95 transition-all">
                        🎨 이대로 그림 그리기!
                    </button>
                </div>
            </div>
        </div>

        <div id="stageBook" class="hidden-stage fade-in w-full h-full flex flex-col items-center">
            <div class="text-center mb-6">
                <span class="text-sm font-bold tracking-widest text-amber-400 uppercase drop-shadow-md">✨ 고대의 마법 동화책 ✨</span>
                <p class="text-sm text-stone-400 mt-1">종이 양 끝 모서리를 눌러 책장을 넘기세요</p>
            </div>

            <div class="relative w-full max-w-4xl aspect-[8/5] bg-transparent flex justify-center items-center preserve-3d" style="perspective: 2500px;" id="bookContainer">

                <div id="staticLeft" class="w-1/2 h-full absolute left-0 z-10 preserve-3d"></div>
                <div id="staticRight" class="w-1/2 h-full absolute right-0 z-10 preserve-3d"></div>

                <div class="absolute left-1/2 top-0 bottom-0 w-16 -ml-8 book-spine z-15 pointer-events-none"></div>

                <div id="prevCorner" class="absolute bottom-0 left-0 w-28 h-28 z-30 cursor-pointer group" onclick="turnPage('prev')">
                    <div class="absolute bottom-0 left-0 w-0 h-0 corner-left-fold"></div>
                    <span class="absolute bottom-1 left-3 text-[12px] font-bold text-stone-700 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">이전</span>
                </div>

                <div id="nextCorner" class="absolute bottom-0 right-0 w-28 h-28 z-30 cursor-pointer group" onclick="turnPage('next')">
                    <div class="absolute bottom-0 right-0 w-0 h-0 corner-right-fold"></div>
                    <span class="absolute bottom-1 right-3 text-[12px] font-bold text-stone-700 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">다음</span>
                </div>

                <!-- 만족도 별점 위젯 (마지막 페이지 "THE END" 아래, 왼쪽 페이지 위에 오버레이) -->
                <div id="ratingContainer" class="absolute left-0 w-1/2 z-[25] hidden flex flex-col items-center gap-2 px-6 opacity-0 transition-opacity duration-1000 pointer-events-none" style="top: 60%;">
                    <p class="pointer-events-auto text-base text-amber-100/90 mb-1 font-semibold text-center drop-shadow-md">이야기가 마음에 드셨나요?<br>별점을 남겨주세요</p>
                    <div class="flex gap-1 mb-1 pointer-events-auto" id="starRating">
                        <button type="button" class="star-btn text-3xl text-yellow-400 hover:scale-110 transition-transform" data-value="1" onclick="setRating(1)">★</button>
                        <button type="button" class="star-btn text-3xl text-yellow-400 hover:scale-110 transition-transform" data-value="2" onclick="setRating(2)">★</button>
                        <button type="button" class="star-btn text-3xl text-yellow-400 hover:scale-110 transition-transform" data-value="3" onclick="setRating(3)">★</button>
                        <button type="button" class="star-btn text-3xl text-yellow-400 hover:scale-110 transition-transform" data-value="4" onclick="setRating(4)">★</button>
                        <button type="button" class="star-btn text-3xl text-yellow-400 hover:scale-110 transition-transform" data-value="5" onclick="setRating(5)">★</button>
                    </div>
                    <p id="ratingSavedText" class="pointer-events-auto text-xs text-amber-300 h-4 opacity-0 transition-opacity duration-500">저장되었습니다 ✅</p>
                </div>
            </div>

            <div id="restartBtnContainer" class="mt-8 flex justify-center hidden opacity-0 transition-opacity duration-1000 w-full">
                <button type="button" onclick="location.reload()" class="w-1/2 max-w-sm bg-gradient-to-r from-amber-700 to-yellow-600 hover:from-amber-600 hover:to-yellow-500 text-amber-50 text-xl font-bold py-4 rounded-xl border border-amber-400/50 shadow-[0_0_30px_rgba(217,119,6,0.4)] transition-all flex items-center justify-center gap-2">
                    처음부터 다시 만들기 🔄
                </button>
            </div>
        </div>

    </div>

    <div id="customAlert" class="fixed inset-0 bg-stone-900/60 backdrop-blur-sm hidden flex items-center justify-center z-50 fade-in">
        <div class="bg-white rounded-[24px] p-8 max-w-sm w-full mx-4 shadow-2xl text-center">
            <div class="w-16 h-16 bg-amber-100 text-amber-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-8 h-8"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" /></svg>
            </div>
            <h3 class="text-3xl font-bold text-stone-800 mb-2">동화 생성 시작!</h3>
            <p class="text-stone-500 text-lg mb-6">입력하신 정보로 예쁜 동화를<br>만들 준비를 마쳤어요.</p>
            <button type="button" onclick="closeAlertAndLoad()" class="w-full bg-amber-400 hover:bg-amber-300 text-stone-900 font-bold py-4 rounded-[18px] transition-all text-xl">
                동화 만들기
            </button>
        </div>
    </div>

    <script>
        let heroName = "주인공";
        let currentSpread = 0;
        let isAnimating = false;
        let spreads = [];

        // 초안 검토 단계에서 쓰는 상태값 (텍스트만 있고 아직 그림은 없는 상태)
        let currentFairytaleId = null;
        let draftPages = [];
        let currentGuideText = "";

        // --- 생성될 동화의 언어 선택 (ko/en) ---
        // 이 버튼은 stage3 화면 자체의 언어를 바꾸는 것이 아니라,
        // AI가 만들어줄 동화(제목 포함 본문)를 한국어로 만들지 영어로 만들지 선택하는 용도입니다.
        let storyLanguage = 'ko';

        function setStoryLanguage(lang) {
            storyLanguage = lang;
            document.getElementById('langKoBtn').classList.toggle('active', lang === 'ko');
            document.getElementById('langEnBtn').classList.toggle('active', lang === 'en');
        }

        function goToStage(stageNumber) {
            document.getElementById('stage1').classList.add('hidden-stage');
            document.getElementById('stage2').classList.add('hidden-stage');
            document.getElementById('stage3').classList.add('hidden-stage');
            document.getElementById('stageLoading').classList.add('hidden-stage');
            document.getElementById('stageDraft').classList.add('hidden-stage');
            document.getElementById('stageBook').classList.add('hidden-stage');
            document.getElementById('stage' + stageNumber).classList.remove('hidden-stage');

            // 입력 스테이지(1/2/3)에 맞춰 뒷배경도 숲 입구 → 동굴 입구 → 보물의 방으로 전환
            const backdrop = document.getElementById('sceneBackdrop');
            if (backdrop) {
                backdrop.classList.remove('scene-forest', 'scene-cave', 'scene-vault');
                if (stageNumber === 1) backdrop.classList.add('scene-forest');
                else if (stageNumber === 2) backdrop.classList.add('scene-cave');
                else if (stageNumber === 3) backdrop.classList.add('scene-vault');
            }
        }

        function submitForm() {
            document.getElementById('customAlert').classList.remove('hidden');
            const nameInput = document.getElementById('heroNameInput');
            if(nameInput && nameInput.value) { heroName = nameInput.value; }
        }

        async function closeAlertAndLoad() {
            document.getElementById('customAlert').classList.add('hidden');

            // 던전 테마로 백그라운드 및 컨테이너 스타일 변경 (몰입감 업!)
            document.body.classList.add('bg-dungeon-theme');

            const mainBox = document.getElementById('mainBox');
            mainBox.classList.remove('bg-white', 'border-stone-200', 'shadow-2xl');
            mainBox.classList.add('bg-black/40', 'border-[#3b2313]/50', 'backdrop-blur-md', 'shadow-[0_0_80px_rgba(0,0,0,0.9)]');

            goToStage('Loading');
            document.getElementById('loadingTitle').innerText = "이야기를 쓰는 중...";
            
            // 초안 생성 시에는 가이드 텍스트 숨김
            const guideContainer = document.getElementById('guideTextContainer');
            if(guideContainer) {
                guideContainer.classList.add('hidden');
                guideContainer.classList.remove('opacity-100');
            }
            
            startProgressBar();

            // 1단계: 텍스트 초안만 빠르게 생성합니다. 그림은 아직 그리지 않습니다.
            // 진행바는 실제 완성 여부와 상관없이 95%에서 멈춰 기다리고,
            // 생성이 실제로 끝난 뒤에야 100%로 채워집니다.
            await generateDraft();
            await finishProgressBar();

            // 초안 검토 단계는 입력 폼(max-w-xl)보다 넓게 보여줘서 이야기를 읽기 편하게 합니다.
            mainBox.classList.replace('max-w-xl', 'max-w-3xl');
            goToStage('Draft');
        }

        let _progressInterval = null;
        let _currentProgress = 0;
        let isRealtimeStatus = false;

        // 진행률 구간별 안내 문구. 실제 생성이 보통 1~2분 걸리기 때문에,
        // 각 구간에서 충분히 오래 머무르며 "기다려주세요" 느낌을 주도록 구성했습니다.
        const LOADING_PHASES = [
            { at: 0,  phase: "주문 외우는 중... 🔮",              status: "신비로운 동화를 준비하고 있어요" },
            { at: 25, phase: "고대의 마법 잉크 섞는 중... 🖋️",     status: "보물창고의 비밀을 그리고 있어요. 조금만 기다려주세요" },
            { at: 50, phase: "삽화를 그리는 중... 🎨",             status: "그림이 절반쯤 완성됐어요. 조금 더 기다려주세요" },
            { at: 75, phase: "가죽 표지 덮는 중... 📖",            status: "마법의 고서가 거의 완성되었어요!" },
            { at: 92, phase: "마지막 마법을 새기는 중... ✨",       status: "곧 완성됩니다. 아주 조금만 기다려주세요!" },
        ];

        function startProgressBar() {
            _currentProgress = 0;
            const progressBar = document.getElementById('progressBar');
            const progressPercent = document.getElementById('progressPercent');
            const loadingPhase = document.getElementById('loadingPhase');
            const loadingStatusText = document.getElementById('loadingStatusText');
            let phaseIdx = 0;

            function render() {
                progressBar.style.width = _currentProgress + '%';
                progressPercent.innerText = Math.floor(_currentProgress) + '%';
                while (phaseIdx < LOADING_PHASES.length - 1 && _currentProgress >= LOADING_PHASES[phaseIdx + 1].at) {
                    phaseIdx++;
                }
                loadingPhase.innerText = LOADING_PHASES[phaseIdx].phase;
                if (!isRealtimeStatus) {
                    loadingStatusText.innerText = LOADING_PHASES[phaseIdx].status;
                }
            }
            render();

            // 구간이 올라갈수록 증가 속도를 늦춰서, 실제 생성 시간(약 1~2분)에 맞춰
            // 25% → 50% → 75% → 92%에서 각각 충분히 머무르다가 서서히 나아가도록 합니다.
            clearInterval(_progressInterval);
            _progressInterval = setInterval(() => {
                let step;
                if (_currentProgress < 25) step = 1.2;
                else if (_currentProgress < 50) step = 0.6;
                else if (_currentProgress < 75) step = 0.35;
                else if (_currentProgress < 92) step = 0.2;
                else step = 0.05; // 92% 근처에서는 실제 생성이 끝날 때까지 거의 멈춰서 기다림

                // 실시간 상태 메시지가 나오는 '그림 생성' 단계는 매우 오래 걸리므로 속도를 1/4로 줄입니다.
                if (isRealtimeStatus) {
                    step = step * 0.25;
                }

                _currentProgress = Math.min(_currentProgress + step, 95);
                render();
            }, 200);
        }

        function finishProgressBar() {
            return new Promise((resolve) => {
                clearInterval(_progressInterval);
                _currentProgress = 100;
                document.getElementById('progressBar').style.width = '100%';
                document.getElementById('progressPercent').innerText = '100%';
                document.getElementById('loadingPhase').innerText = "마법의 책이 완성되었어요! 🎉";
                document.getElementById('loadingStatusText').innerText = "이야기 속으로 들어가볼까요?";
                setTimeout(resolve, 700);
            });
        }

        let isFetching = false;

        // 아이 프로필 입력값을 백엔드 페이로드 형태로 정리합니다.
        function collectChildPayload() {
            const birthYearElement = document.getElementById('birthYearInput');
            const genderElement = document.querySelector('input[name="gender"]:checked');

            const birthYear = birthYearElement ? parseInt(birthYearElement.value) : NaN;
            const currentYear = new Date().getFullYear();
            const computedAge = (!isNaN(birthYear) && birthYear > 1900 && birthYear <= currentYear)
                ? (currentYear - birthYear)
                : 5;

            return {
                name: document.getElementById('heroNameInput').value || "무명",
                birth_year: (!isNaN(birthYear) && birthYear > 1900 && birthYear <= currentYear) ? birthYear : currentYear - 5,
                gender: genderElement ? (genderElement.value === 'male' ? "남" : "여") : "기타"
            };
        }

        // 동화 조건 입력값을 백엔드 페이로드 형태로 정리합니다.
        function collectTalePayload() {
            return {
                appearance: document.getElementById('appearanceInput').value || "통통하고 귀여움",
                personality: document.getElementById('personalityInput').value || "활발하고 호기심이 많음",
                place: document.getElementById('placeInput').value || "신비로운 요정의 숲",
                time_period: document.getElementById('timePeriodInput').value || "아주 먼 옛날",
                mood: document.getElementById('moodInput').value || "몽환적이고 따뜻함",
                problem_situation: document.getElementById('problemTextarea').value || "작은 걱정거리",
                language: storyLanguage || "ko"
            };
        }

        // 1단계: 아이 프로필을 등록하고, 텍스트 초안(그림 없이 4페이지 분량)만 생성합니다.
        // 백엔드 계약: POST /children/{childId}/fairytales/draft
        //   응답 예시: { "id": "...", "title": "...", "pages": [{ "text": "..." }, ...] }
        async function generateDraft() {
            if (isFetching) {
                console.log("이미 요청을 처리 중입니다. 중복 요청을 무시합니다.");
                return;
            }
            isFetching = true;

            try {
                const childRes = await fetch("__BACKEND_URL__/children", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(collectChildPayload())
                });
                if (!childRes.ok) throw new Error("아이 프로필 등록 통신 실패");
                const childData = await childRes.json();
                const newChildId = childData.id || childData._id;

                const response = await fetch(`__BACKEND_URL__/children/${newChildId}/fairytales/draft`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(collectTalePayload())
                });
                if (!response.ok) throw new Error("이야기 초안 생성 통신 실패");
                const data = await response.json();

                currentFairytaleId = data.id || data._id;
                draftPages = data.pages || [];
                currentGuideText = data.guide_text || "";
                
                document.getElementById('feedbackLog').innerHTML = '';
                renderDraftPages(draftPages);
            } catch (err) {
                alert("이야기 초안 생성 실패: " + err.message);
                currentFairytaleId = null;
                draftPages = [];
                renderDraftPages(draftPages);
            } finally {
                isFetching = false;
            }
        }

        // 초안 페이지 텍스트를 화면에 그립니다.
        function renderDraftPages(pages) {
            const container = document.getElementById('draftPagesContainer');
            container.innerHTML = '';

            if (!pages.length) {
                const empty = document.createElement('p');
                empty.className = 'text-center text-lg text-stone-400 py-8';
                empty.textContent = '이야기를 불러오지 못했어요. 이전 단계로 돌아가 다시 시도해주세요.';
                container.appendChild(empty);
                return;
            }

            pages.forEach((page, idx) => {
                const card = document.createElement('div');
                card.className = 'bg-stone-50 border border-stone-200 rounded-2xl p-4';

                const label = document.createElement('p');
                label.className = 'text-sm font-bold text-amber-500 mb-2';
                label.textContent = (idx + 1) + '페이지';

                const text = document.createElement('p');
                text.className = 'text-lg text-gray-800 leading-loose whitespace-pre-wrap';
                text.textContent = page.text;

                card.appendChild(label);
                card.appendChild(text);
                container.appendChild(card);
            });
        }

        // 이번 요청에서 반영된 피드백 문구를 기록해서 화면에 남겨둡니다(사용자 확인용).
        function logFeedback(feedback) {
            const log = document.getElementById('feedbackLog');
            const entry = document.createElement('p');
            entry.textContent = '✓ 반영됨: "' + feedback + '"';
            log.appendChild(entry);
        }

        // 2단계: 사용자 피드백을 반영해 텍스트 초안을 다시 씁니다.
        // 백엔드 계약: POST /fairytales/{id}/revise  body: { "feedback": "..." }
        //   응답 형태는 draft 생성 응답과 동일합니다 ({ id, title, pages }).
        async function submitFeedback() {
            const feedbackInput = document.getElementById('feedbackTextarea');
            const feedback = feedbackInput.value.trim();

            if (!feedback) {
                alert("어떻게 고치고 싶은지 먼저 적어주세요. 수정할 게 없다면 '이대로 그림 그리기!'를 눌러주세요.");
                return;
            }
            if (!currentFairytaleId || isFetching) return;
            isFetching = true;

            goToStage('Loading');
            document.getElementById('loadingTitle').innerText = "이야기를 고치는 중...";
            startProgressBar();

            try {
                const response = await fetch(`__BACKEND_URL__/fairytales/${currentFairytaleId}/revise`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ feedback })
                });
                if (!response.ok) throw new Error("이야기 수정 통신 실패");
                const data = await response.json();

                draftPages = data.pages || [];
                logFeedback(feedback);
                feedbackInput.value = '';
                await finishProgressBar();
                renderDraftPages(draftPages);
            } catch (err) {
                alert("이야기 수정 실패: " + err.message);
            } finally {
                isFetching = false;
                goToStage('Draft');
            }
        }

        // 3단계: 텍스트가 확정되면 그림을 그리고 최종 동화책(텍스트+이미지)을 받아옵니다.
        // 백엔드 계약: POST /fairytales/{id}/finalize
        //   응답 형태는 기존 완성본 조회(GET /fairytales/{id})와 동일합니다
        //   ({ id, title, content_json: [{ text, image_url, is_cover }, ...] }).
        async function finalizeStory() {
            if (!currentFairytaleId || isFetching) return;
            isFetching = true;

            goToStage('Loading');
            document.getElementById('loadingTitle').innerText = "삽화를 그리는 중...";
            const statusText = document.getElementById('loadingStatusText');
            statusText.innerText = "서버와 연결을 준비 중입니다...";
            statusText.style.display = 'block'; // 명시적으로 보이게 함
            
            // 삽화 생성 단계: 저장해둔 육아 지침 노출
            const guideContainer = document.getElementById('guideTextContainer');
            const guideContent = document.getElementById('guideTextContent');
            if (guideContainer && guideContent && currentGuideText) {
                guideContent.innerText = currentGuideText;
                guideContainer.classList.remove('hidden');
                // 부드러운 나타남 효과
                setTimeout(() => { guideContainer.classList.add('opacity-100'); }, 100);
            }
            
            isRealtimeStatus = true;
            startProgressBar();

            try {
                const response = await fetch(`__BACKEND_URL__/fairytales/${currentFairytaleId}/finalize`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                if (!response.ok) throw new Error("그림 생성 통신 실패");
                
                // SSE 스트림 읽기
                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";
                let finalData = null;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\\n');
                    buffer = lines.pop(); // 마지막에 덜 끝난 조각만 보관

                    for (const line of lines) {
                        const trimmed = line.trim();
                        if (trimmed === '') continue;
                        if (trimmed.startsWith('data: ')) {
                            const jsonStr = trimmed.substring(6);
                            try {
                                const parsed = JSON.parse(jsonStr);
                                if (parsed.status === "progress") {
                                    statusText.innerText = parsed.message;
                                } else if (parsed.status === "done") {
                                    finalData = parsed.result;
                                } else if (parsed.status === "error") {
                                    throw new Error(parsed.message);
                                }
                            } catch(e) {
                                console.warn("SSE 파싱 에러:", e, "원본:", jsonStr);
                            }
                        }
                    }
                }

                if (!finalData) throw new Error("최종 동화 데이터를 받지 못했습니다.");
                const data = finalData;

                spreads = buildSpreadsFromFairytale(data);
                currentSpread = 0;

                const storyId = data.id || data._id;
                if (storyId) {
                    saveToHistory({
                        id: storyId,
                        title: data.title || "동화책",
                        heroName: heroName,
                        language: storyLanguage,
                        createdAt: new Date().toISOString()
                    });
                }

                await finishProgressBar();
                isRealtimeStatus = false;

                const mainBox = document.getElementById('mainBox');
                mainBox.classList.remove('max-w-xl', 'max-w-3xl');
                mainBox.classList.add('max-w-5xl');
                renderStaticSpread();
                updateCorners();
                goToStage('Book');
            } catch (err) {
                alert("그림 생성 실패: " + err.message);
                goToStage('Draft');
            } finally {
                isFetching = false;
                isRealtimeStatus = false;
            }
        }

        // fairytale API 응답(data)을 책장 데이터(spreads 배열)로 변환합니다.
        // 방금 생성한 동화든, 히스토리에서 다시 불러온 동화든 이 함수 하나로 처리합니다.
        function buildSpreadsFromFairytale(data) {
            let contentList = [];
            if (data.content) {
                // 중요: shift() 호출로 원본 배열이 훼손되는 것을 막기 위해 얕은 복사(Spread)를 사용합니다.
                contentList = Array.isArray(data.content) ? [...data.content] : [];
            } else if (data.content_json) {
                try { contentList = JSON.parse(data.content_json); } catch(e) {}
            }
            const result = [];

            let coverImg = 'https://placehold.co/400x500/1a1209/d4a373?text=Cover';
            if (contentList.length > 0 && (contentList[0].is_cover || contentList[0].page === 0)) {
                const cover = contentList.shift();
                coverImg = "http://127.0.0.1:8000" + cover.image_url;
            }

            result.push({
                left: { type: 'empty' },
                right: { type: 'cover', title: data.title || "동화책", img: coverImg }
            });

            for (let i = 0; i < contentList.length; i++) {
                const page = contentList[i];
                result.push({
                    left: { type: 'text', text: page.text },
                    right: { type: 'image', img: page.image_url ? "http://127.0.0.1:8000" + page.image_url : 'https://placehold.co/400x500/e6d8ba/5c4033' }
                });
            }

            result.push({
                left: { type: 'backcover' },
                right: { type: 'empty' }
            });

            return result;
        }

        // ------------------------------------------------------------------
        // 내가 만든 동화 히스토리 (햄버거 메뉴) — 백엔드에 "내 이야기 목록" API가 없어서,
        // 브라우저 localStorage에 fairytale id/제목만 기록해두고, 열람 시 그 id로
        // 실제 내용을(GET /fairytales/{id}) 다시 불러오는 방식입니다.
        // ------------------------------------------------------------------
        const HISTORY_KEY = 'fairytale_history';
        const HISTORY_MAX = 30;

        function getHistory() {
            try {
                const raw = localStorage.getItem(HISTORY_KEY);
                return raw ? JSON.parse(raw) : [];
            } catch (e) {
                return [];
            }
        }

        function saveToHistory(entry) {
            try {
                let hist = getHistory().filter(h => h.id !== entry.id);
                hist.unshift(entry);
                if (hist.length > HISTORY_MAX) hist = hist.slice(0, HISTORY_MAX);
                localStorage.setItem(HISTORY_KEY, JSON.stringify(hist));
            } catch (e) {
                console.warn('히스토리 저장 실패:', e);
            }
        }

        function openHistoryDrawer() {
            renderHistoryList();
            document.getElementById('historyOverlay').classList.remove('hidden');
            document.getElementById('historyDrawer').classList.remove('-translate-x-full');
        }

        function closeHistoryDrawer() {
            document.getElementById('historyOverlay').classList.add('hidden');
            document.getElementById('historyDrawer').classList.add('-translate-x-full');
        }

        function renderHistoryList() {
            const container = document.getElementById('historyList');
            container.innerHTML = '';
            const hist = getHistory();

            if (hist.length === 0) {
                const empty = document.createElement('p');
                empty.className = 'text-center text-stone-400 mt-10 text-sm leading-relaxed';
                empty.textContent = '아직 만든 동화가 없어요. 첫 번째 이야기를 만들어보세요! ✨';
                container.appendChild(empty);
                return;
            }

            hist.forEach(h => {
                const dateLabel = h.createdAt
                    ? new Date(h.createdAt).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
                    : '';

                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'w-full text-left bg-white hover:bg-amber-50 border border-stone-200 hover:border-amber-300 rounded-2xl p-4 transition-all';

                const titleP = document.createElement('p');
                titleP.className = 'font-bold text-stone-800 truncate';
                titleP.textContent = h.title || '동화책';

                const metaP = document.createElement('p');
                metaP.className = 'text-xs text-stone-400 mt-1';
                metaP.textContent = [h.heroName, dateLabel].filter(Boolean).join(' · ');

                btn.appendChild(titleP);
                btn.appendChild(metaP);
                btn.addEventListener('click', () => openHistoryStory(h));
                container.appendChild(btn);
            });
        }

        async function openHistoryStory(entry) {
            closeHistoryDrawer();

            heroName = entry.heroName || "주인공";
            storyLanguage = entry.language || 'ko';
            document.getElementById('langKoBtn').classList.toggle('active', storyLanguage === 'ko');
            document.getElementById('langEnBtn').classList.toggle('active', storyLanguage === 'en');

            document.body.classList.add('bg-dungeon-theme');
            const mainBox = document.getElementById('mainBox');
            mainBox.classList.remove('bg-white', 'border-stone-200', 'shadow-2xl');
            mainBox.classList.add('bg-black/40', 'border-[#3b2313]/50', 'backdrop-blur-md', 'shadow-[0_0_80px_rgba(0,0,0,0.9)]');
            mainBox.classList.remove('max-w-xl', 'max-w-3xl');
            mainBox.classList.add('max-w-5xl');

            goToStage('Loading');
            document.getElementById('loadingTitle').innerText = "예전 이야기를 펼치는 중...";
            document.getElementById('loadingStatusText').innerText = "책장을 찾아오고 있어요";
            document.getElementById('loadingPhase').innerText = "책장을 찾는 중... 📚";
            document.getElementById('progressPercent').innerText = '';
            document.getElementById('progressBar').style.width = '70%';

            try {
                const res = await fetch(`__BACKEND_URL__/fairytales/${entry.id}`);
                if (!res.ok) throw new Error("이야기를 불러오지 못했어요");
                const data = await res.json();

                spreads = buildSpreadsFromFairytale(data);
                currentSpread = 0;
                document.getElementById('progressBar').style.width = '100%';

                renderStaticSpread();
                updateCorners();
                goToStage('Book');
            } catch (err) {
                alert("이야기를 불러오지 못했어요: " + err.message);
                goToStage(1);
            }
        }

        function renderPageHTML(pageData, side) {
            if (pageData.type === 'empty') return '<div class="w-full h-full bg-transparent"></div>';

            const roundClass = side === 'left' ? 'rounded-l-[14px]' : 'rounded-r-[14px]';
            const isCover = pageData.type === 'cover' || pageData.type === 'backcover';

            // 표지면 가죽 클래스, 속지면 파피루스 클래스 적용
            const themeClass = isCover ? 'page-leather border-[#221309]' : 'page-papyrus border-[#b89b72]';
            const hingeClass = isCover
                ? (side === 'left' ? 'border-r-[18px] !border-r-[#1f1007]' : 'border-l-[18px] !border-l-[#1f1007]')
                : (side === 'left' ? 'border-r-[8px] !border-r-[#b89b72]' : 'border-l-[8px] !border-l-[#b89b72]');

            const baseClass = `w-full h-full p-8 flex flex-col items-center justify-center border-2 ${themeClass} ${roundClass} ${hingeClass}`;

            if (pageData.type === 'cover') {
                return `
                <div class="${baseClass}">
                    <div class="w-[90%] h-[90%] border-2 border-dashed border-[#8b5a2b] p-5 flex flex-col items-center justify-center rounded-xl relative before:absolute before:inset-2 before:border before:border-[#6b4226] before:rounded-lg">
                        <img src="${pageData.img}" class="w-full h-3/5 object-cover rounded-md shadow-[0_10px_20px_rgba(0,0,0,0.8)] mb-8 border-4 border-[#2b170a] relative z-10">
                        <h2 class="text-[34px] font-bold text-center text-[#d4af37] leading-tight break-keep tracking-widest drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)] relative z-10">${pageData.title}</h2>
                    </div>
                </div>`;
            }
            if (pageData.type === 'backcover') {
                const endLabel = storyLanguage === 'en' ? '' : `<p class="font-bold text-3xl tracking-widest text-[#a67c52] mb-4">끝</p>`;
                return `
                <div class="${baseClass}">
                    <div class="w-[80%] h-[80%] border-2 border-dashed border-[#5c3a21] flex flex-col items-center justify-center rounded-xl opacity-70">
                        ${endLabel}
                        <p class="text-xl text-[#8b5a2b] font-serif">THE END</p>
                    </div>
                </div>`;
            }
            if (pageData.type === 'text') {
                return `
                <div class="${baseClass} relative">
                    <div class="absolute inset-5 border border-[#c8aa82] rounded-sm pointer-events-none opacity-60"></div>
                    <div class="relative z-10 w-full h-[85%] overflow-y-auto custom-scrollbar px-8 py-4">
                        <p class="text-[20px] text-[#4a2e15] leading-[2.1] text-justify break-keep font-medium">
                            ${pageData.text}
                        </p>
                    </div>
                </div>`;
            }
            if (pageData.type === 'image') {
                return `
                <div class="${baseClass} relative">
                    <div class="absolute inset-5 border border-[#c8aa82] rounded-sm pointer-events-none opacity-60"></div>
                    <img src="${pageData.img}" class="w-full h-full object-cover rounded-sm shadow-[inset_0_0_20px_rgba(0,0,0,0.3)] border border-[#a6865c] p-1.5 bg-[#cfb58f]/50">
                </div>`;
            }
            return '';
        }

        function renderStaticSpread() {
            document.getElementById('staticLeft').innerHTML = renderPageHTML(spreads[currentSpread].left, 'left');
            document.getElementById('staticRight').innerHTML = renderPageHTML(spreads[currentSpread].right, 'right');
        }

        function updateCorners() {
            const nextCorner = document.getElementById('nextCorner');
            const prevCorner = document.getElementById('prevCorner');
            const restartBtn = document.getElementById('restartBtnContainer');
            const ratingContainer = document.getElementById('ratingContainer');

            if (isAnimating) {
                nextCorner.style.display = 'none';
                prevCorner.style.display = 'none';
                return;
            }

            nextCorner.style.display = currentSpread < spreads.length - 1 ? 'block' : 'none';
            prevCorner.style.display = currentSpread > 0 ? 'block' : 'none';

            if (currentSpread === spreads.length - 1) {
                restartBtn.classList.remove('hidden');
                ratingContainer.classList.remove('hidden');
                setTimeout(() => {
                    restartBtn.classList.remove('opacity-0');
                    ratingContainer.classList.remove('opacity-0');
                }, 100);
            } else {
                restartBtn.classList.add('hidden', 'opacity-0');
                ratingContainer.classList.add('hidden', 'opacity-0');
            }
        }

        // --- 만족도 별점 (0~5개) ---
        let currentRating = 0;

        function setRating(value) {
            // 같은 별을 다시 누르면 0점(선택 해제)으로 초기화
            currentRating = (currentRating === value) ? 0 : value;
            renderStars();
            saveRating();
        }

        function renderStars() {
            document.querySelectorAll('#starRating .star-btn').forEach(btn => {
                const v = parseInt(btn.dataset.value, 10);
                if (v <= currentRating) {
                    btn.classList.remove('text-stone-600');
                    btn.classList.add('text-amber-400');
                } else {
                    btn.classList.remove('text-amber-400');
                    btn.classList.add('text-stone-600');
                }
            });
        }

        function saveRating() {
            const data = {
                heroName: heroName,
                language: storyLanguage,
                rating: currentRating,
                savedAt: new Date().toISOString()
            };
            try {
                localStorage.setItem('fairytale_satisfaction_rating', JSON.stringify(data));
            } catch (e) {
                console.warn('만족도 저장 실패:', e);
            }

            const savedText = document.getElementById('ratingSavedText');
            savedText.innerText = currentRating === 0 ? '평가가 초기화되었습니다' : `${currentRating}점으로 저장되었습니다 ✅`;
            savedText.classList.remove('opacity-0');
            clearTimeout(saveRating._timer);
            saveRating._timer = setTimeout(() => { savedText.classList.add('opacity-0'); }, 1800);
        }

        function turnPage(direction) {
            if (isAnimating) return;
            if (direction === 'next' && currentSpread >= spreads.length - 1) return;
            if (direction === 'prev' && currentSpread <= 0) return;

            isAnimating = true;
            updateCorners();

            const bookContainer = document.getElementById('bookContainer');
            const nextSpreadIdx = direction === 'next' ? currentSpread + 1 : currentSpread - 1;

            const flipper = document.createElement('div');
            flipper.className = 'absolute top-0 h-full w-1/2 preserve-3d z-20 transition-transform duration-[850ms] ease-in-out';

            const flipperFront = document.createElement('div');
            const flipperBack = document.createElement('div');
            flipperFront.className = 'absolute inset-0 backface-hidden shadow-[0_0_20px_rgba(0,0,0,0.3)]';
            flipperBack.className = 'absolute inset-0 backface-hidden shadow-[0_0_20px_rgba(0,0,0,0.3)]';

            if (direction === 'next') {
                flipper.style.left = '50%';
                flipper.style.transformOrigin = 'left center';

                flipperFront.innerHTML = renderPageHTML(spreads[currentSpread].right, 'right');
                flipperBack.innerHTML = renderPageHTML(spreads[nextSpreadIdx].left, 'left');
                flipperBack.style.transform = 'rotateY(180deg)';

                flipper.appendChild(flipperFront);
                flipper.appendChild(flipperBack);
                bookContainer.appendChild(flipper);

                document.getElementById('staticLeft').innerHTML = renderPageHTML(spreads[currentSpread].left, 'left');
                document.getElementById('staticRight').innerHTML = renderPageHTML(spreads[nextSpreadIdx].right, 'right');

                requestAnimationFrame(() => {
                    requestAnimationFrame(() => { flipper.style.transform = 'rotateY(-180deg)'; });
                });

            } else {
                flipper.style.left = '0';
                flipper.style.transformOrigin = 'right center';

                flipperFront.innerHTML = renderPageHTML(spreads[currentSpread].left, 'left');
                flipperBack.innerHTML = renderPageHTML(spreads[nextSpreadIdx].right, 'right');
                flipperBack.style.transform = 'rotateY(-180deg)';

                flipper.appendChild(flipperFront);
                flipper.appendChild(flipperBack);
                bookContainer.appendChild(flipper);

                document.getElementById('staticLeft').innerHTML = renderPageHTML(spreads[nextSpreadIdx].left, 'left');
                document.getElementById('staticRight').innerHTML = renderPageHTML(spreads[currentSpread].right, 'right');

                requestAnimationFrame(() => {
                    requestAnimationFrame(() => { flipper.style.transform = 'rotateY(180deg)'; });
                });
            }

            setTimeout(() => {
                flipper.remove();
                currentSpread = nextSpreadIdx;
                renderStaticSpread();
                isAnimating = false;
                updateCorners();
            }, 850);
        }
    </script>
</body>
</html>
"""

# HTML 템플릿에 백엔드 주소 및 스테이지별 배경 이미지 주입
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api")
FINAL_HTML = (
    HTML_TEMPLATE.replace("__BACKEND_URL__", BACKEND_URL)
    .replace("__BG_FOREST__", load_image_data_uri("bg_forest.jpg"))
    .replace("__SMILE_LOGO__", load_image_data_uri("SMILEimage.png", mime="image/png"))
    .replace("__BG_CAVE__", load_image_data_uri("bg_cave.jpg"))
    .replace("__BG_VAULT__", load_image_data_uri("bg_vault.jpg"))
)

components.html(FINAL_HTML, height=980, scrolling=True)

# ----------------------------------------------------------------------------
# 책 안의 별점(localStorage)을 몇 초마다 자동으로 확인해서 파일에 동기화
# ----------------------------------------------------------------------------
if _SYNC_AVAILABLE:
    # localStorage 값을 새로 확인합니다. (책 안에서 별을 클릭하면 다음 자동 새로고침 때 반영됩니다)
    _refresh_count = st_autorefresh(interval=2000, key="rating_autorefresh")

    # 중요: st_javascript는 커스텀 컴포넌트라서, 같은 코드/같은 key로 다시 호출하면
    # Streamlit이 "이전과 똑같은 요청"으로 보고 실제 JS를 다시 실행하지 않고 이전 값을
    # 재사용할 수 있습니다. 그래서 매 자동 새로고침마다 key 값을 바꿔서, 매번 새로
    # localStorage를 읽어오도록(반드시 재실행되도록) 강제합니다.
    raw = st_javascript(
        "localStorage.getItem('fairytale_satisfaction_rating')",
        key=f"ls_check_{_refresh_count}",
    )

    with st.expander("🔧 동기화 디버그 정보 (문제가 계속되면 이 내용을 알려주세요)"):
        st.write("autorefresh 횟수:", _refresh_count)
        st.write("st_javascript 반환값(raw):", raw)
        st.write("마지막으로 저장 처리한 값:", st.session_state.last_synced_rating_raw)

    if raw and raw != 0 and raw != st.session_state.last_synced_rating_raw:
        try:
            data = json.loads(raw)
            browser_ts = data.get("savedAt", "")

            # 세션 메모리(last_synced_rating_raw)는 브라우저 재연결/새로고침 시 초기화될 수 있어
            # 그것만 믿으면 같은 별점이 여러 번 저장되는 문제가 생깁니다.
            # 그래서 실제 파일에 이미 이 이벤트(rated_at_browser 시각)가 저장되어 있는지
            # 한 번 더 확인한 뒤에만 새로 저장합니다.
            if not already_saved(browser_ts):
                record = {
                    "hero_name": data.get("heroName", ""),
                    "language": data.get("language", ""),
                    "rating": data.get("rating", 0),
                    "rated_at_browser": browser_ts,
                    "synced_at": datetime.now().isoformat(timespec="seconds"),
                }
                save_rating_record(record)
                st.toast(
                    f"⭐ {record['hero_name']} ({record['language']}) - {record['rating']}점이 "
                    f"satisfaction_ratings.json에 저장되었습니다",
                    icon="✅",
                )

            # 파일에 이미 있든 새로 저장했든, 이번 값은 처리 완료로 표시
            st.session_state.last_synced_rating_raw = raw
        except (json.JSONDecodeError, TypeError):
            pass

    st.caption(
        "책 마지막 페이지의 별점을 누르면 몇 초 안에 이 폴더의 satisfaction_ratings.json에 "
        "이름·언어·별점이 자동으로 저장됩니다."
    )
else:
    st.warning(
        "별점을 파일로 자동 저장하려면 다음 패키지가 필요합니다: "
        "`pip install streamlit-javascript streamlit-autorefresh` 설치 후 앱을 다시 실행해 주세요. "
        "(설치 전에는 책 안의 별점이 브라우저에만 저장됩니다.)"
    )