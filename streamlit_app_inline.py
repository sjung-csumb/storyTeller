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

import json
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_javascript import st_javascript
    from streamlit_autorefresh import st_autorefresh
    _SYNC_AVAILABLE = True
except ImportError:
    _SYNC_AVAILABLE = False

RATINGS_FILE = Path(__file__).parent / "satisfaction_ratings.json"

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
    .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; max-width: 100% !important; }
    #MainMenu, header, footer { visibility: hidden; height: 0; }
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
    </style>
</head>
<body class="bg-stone-100 text-gray-800 min-h-screen flex flex-col items-center justify-center p-6 transition-colors duration-1000">

    <div id="mainBox" class="w-full max-w-xl bg-white rounded-3xl p-10 shadow-2xl border border-stone-200 relative overflow-hidden transition-all duration-1000 ease-in-out">
        <!-- 1. stage1 주인공 이름 -->
        <div id="stage1" class="fade-in">
            <div class="text-center mb-8">
                <div class="flex justify-center items-center gap-2 mb-2">
                    <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span class="w-2 h-2 rounded-full bg-gray-200"></span>
                    <span class="w-2 h-2 rounded-full bg-gray-200"></span>
                </div>
                <span class="text-xs font-semibold tracking-wider text-amber-500 uppercase">STAGE 1 / 3</span>
                <h1 class="text-3xl font-bold mt-1 text-gray-800">📖 AI 동화만들기 프로젝트</h1>
                <p class="text-2sm text-gray-500 mt-1">이야기의 주인공을 설정해 주세요</p>
            </div>

            <form class="space-y-6" onsubmit="event.preventDefault(); goToStage(2);">
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2">주인공 이름</label>
                    <input type="text" id="heroNameInput" placeholder="예: 김사과" class="w-full bg-stone-50 border border-stone-200 rounded-[20px] px-4 py-3 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>

                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2">나이</label>
                    <div class="grid grid-cols-4 gap-2">
                        <label class="relative flex items-center justify-center bg-stone-50 border border-stone-200 rounded-xl py-1.5 px-2 cursor-pointer hover:border-stone-300 transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="age" value="3" class="absolute opacity-0 peer">
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">3세</span>
                        </label>
                        <label class="relative flex items-center justify-center bg-stone-50 border border-stone-200 rounded-xl py-1.5 px-2 cursor-pointer hover:border-stone-300 transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="age" value="4" class="absolute opacity-0 peer">
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">4세</span>
                        </label>
                        <label class="relative flex items-center justify-center bg-stone-50 border border-stone-200 rounded-xl py-1.5 px-2 cursor-pointer hover:border-stone-300 transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="age" value="5" class="absolute opacity-0 peer">
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">5세</span>
                        </label>
                        <label class="relative flex items-center justify-center bg-stone-50 border border-stone-200 rounded-xl py-1.5 px-2 cursor-pointer hover:border-stone-300 transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="age" value="6" class="absolute opacity-0 peer">
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">6세</span>
                        </label>
                    </div>
                </div>

                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2">성별</label>
                    <div class="flex gap-2">
                        <label class="flex-1 relative flex items-center justify-center bg-stone-50 border border-stone-200 rounded-xl p-3 cursor-pointer hover:border-stone-300 transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="gender" value="male" class="absolute opacity-0 peer">
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">남</span>
                        </label>
                        <label class="flex-1 relative flex items-center justify-center bg-stone-50 border border-stone-200 rounded-xl p-3 cursor-pointer hover:border-stone-300 transition-all has-[:checked]:border-amber-400 has-[:checked]:bg-amber-50">
                            <input type="radio" name="gender" value="female" class="absolute opacity-0 peer">
                            <span class="text-lg font-medium text-gray-500 peer-checked:text-amber-600 peer-checked:font-bold">여</span>
                        </label>
                    </div>
                </div>

                <button type="submit" class="w-full bg-amber-400 hover:bg-amber-300 text-xl text-gray-900 font-bold py-4 rounded-[20px] shadow-sm hover:shadow-md transition-all mt-6 flex items-center justify-center gap-2">
                    다음 단계로 이동 ➜
                </button>
            </form>
        </div>

        <div id="stage2" class="hidden-stage fade-in">
            <div class="text-center mb-8">
                <div class="flex justify-center items-center gap-2 mb-2">
                    <span class="w-2 h-2 rounded-full bg-gray-200"></span>
                    <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span class="w-2 h-2 rounded-full bg-gray-200"></span>
                </div>
                <span class="text-xs font-semibold tracking-wider text-amber-500 uppercase">STAGE 2 / 3</span>
                <h2 class="text-3xl font-bold mt-1 text-gray-800">어떤 이야기인가요?</h2>
                <p class="text-2xs text-gray-500 mt-1">주인공과 배경에 대해 더 자세히 알려주세요</p>
            </div>
            <form class="space-y-4" onsubmit="event.preventDefault(); goToStage(3);">
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-1">주인공의 외형</label>
                    <input type="text" placeholder="예: 빨간 모자를 쓰고 있어요" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-1">주인공의 성격</label>
                    <input type="text" placeholder="예: 호기심이 많고 용감해요" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xl font-semibold text-gray-700 mb-1">장소</label>
                        <input type="text" placeholder="예: 깊은 숲속" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                    </div>
                    <div>
                        <label class="block text-xl font-semibold text-gray-700 mb-1">시대</label>
                        <input type="text" placeholder="예: 아주 먼 옛날" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                    </div>
                </div>
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-1">분위기</label>
                    <input type="text" placeholder="예: 신비롭고 따뜻한 느낌" class="w-full bg-stone-50 border border-stone-200 rounded-[16px] px-4 py-2.5 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors" required>
                </div>
                <div class="flex gap-3 mt-6">
                    <button type="button" onclick="goToStage(1)" class="w-1/3 bg-stone-100 hover:bg-stone-200 text-xl text-gray-600 font-bold py-4 rounded-[20px] transition-all flex items-center justify-center">이전</button>
                    <button type="submit" class="w-2/3 bg-amber-400 hover:bg-amber-300 text-xl text-gray-900 font-bold py-4 rounded-[20px] shadow-sm hover:shadow-md transition-all flex items-center justify-center gap-2">다음 단계로 ➜</button>
                </div>
            </form>
        </div>

        <div id="stage3" class="hidden-stage fade-in relative">
            <!-- 언어 선택 토글 (KO/EN) -->
            <div class="absolute top-0 right-0 flex items-center gap-1 bg-stone-100 border border-stone-200 rounded-full p-1 z-10">
                <button type="button" id="langKoBtn" onclick="setStoryLanguage('ko')" class="lang-toggle-btn active px-3 py-1.5 rounded-full text-sm font-bold">KO</button>
                <button type="button" id="langEnBtn" onclick="setStoryLanguage('en')" class="lang-toggle-btn px-3 py-1.5 rounded-full text-sm font-bold">EN</button>
            </div>

            <div class="text-center mb-8">
                <div class="flex justify-center items-center gap-2 mb-2">
                    <span class="w-2 h-2 rounded-full bg-gray-200"></span>
                    <span class="w-2 h-2 rounded-full bg-gray-200"></span>
                    <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                </div>
                <span class="text-xs font-semibold tracking-wider text-amber-500 uppercase">STAGE 3 / 3</span>
                <h2 class="text-3xl font-bold mt-1 text-gray-800" id="stage3Title">어떤 일이 생겼나요?</h2>
                <p class="text-2xs text-gray-500 mt-1" id="stage3Subtitle">주인공이 겪는 문제나 사건을 적어주세요</p>
            </div>
            <form class="space-y-6" onsubmit="event.preventDefault(); submitForm();">
                <div>
                    <label class="block text-xl font-semibold text-gray-700 mb-2" id="problemLabel">문제 상황</label>
                    <textarea id="problemTextarea" rows="7" placeholder="예: 소중한 장난감을 잃어버려서 슬퍼하고 있어요. 친구들과 어떻게 화해해야 할지 모르겠어요." class="w-full bg-stone-50 border border-stone-200 rounded-[20px] px-4 py-4 text-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors resize-none" required></textarea>
                </div>
                <div class="flex gap-3 mt-6">
                    <button type="button" onclick="goToStage(2)" class="w-1/3 bg-stone-100 hover:bg-stone-200 text-xl text-gray-600 font-bold py-4 rounded-[20px] transition-all flex items-center justify-center" id="prevBtnText">이전</button>
                    <button type="submit" class="w-2/3 bg-orange-400 hover:bg-orange-500 text-xl text-white font-bold py-4 rounded-[20px] shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2" id="submitBtnText">✨ 이야기 만들기!</button>
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
                던전으로 입장하기
            </button>
        </div>
    </div>

    <script>
        let heroName = "주인공";
        let currentSpread = 0;
        let isAnimating = false;
        let spreads = [];

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
            document.getElementById('stageBook').classList.add('hidden-stage');
            document.getElementById('stage' + stageNumber).classList.remove('hidden-stage');
        }

        function submitForm() {
            document.getElementById('customAlert').classList.remove('hidden');
            const nameInput = document.getElementById('heroNameInput');
            if(nameInput && nameInput.value) { heroName = nameInput.value; }
        }

        function closeAlertAndLoad() {
            document.getElementById('customAlert').classList.add('hidden');

            // 던전 테마로 백그라운드 및 컨테이너 스타일 변경 (몰입감 업!)
            document.body.classList.add('bg-dungeon-theme');

            const mainBox = document.getElementById('mainBox');
            mainBox.classList.remove('bg-white', 'border-stone-200', 'shadow-2xl');
            mainBox.classList.add('bg-black/40', 'border-[#3b2313]/50', 'backdrop-blur-md', 'shadow-[0_0_80px_rgba(0,0,0,0.9)]');

            goToStage('Loading');
            startProgressBar();
        }

        function startProgressBar() {
            let progress = 0;
            const progressBar = document.getElementById('progressBar');
            const progressPercent = document.getElementById('progressPercent');
            const loadingPhase = document.getElementById('loadingPhase');
            const loadingStatusText = document.getElementById('loadingStatusText');

            const interval = setInterval(() => {
                progress += Math.floor(Math.random() * 6) + 1;
                if(progress > 100) progress = 100;

                progressBar.style.width = progress + '%';
                progressPercent.innerText = progress + '%';

                if(progress > 30 && progress < 70) {
                    loadingPhase.innerText = "고대의 마법 잉크 섞는 중... 🖋️";
                    loadingStatusText.innerText = "보물창고의 비밀을 그리고 있어요";
                } else if(progress >= 70 && progress < 100) {
                    loadingPhase.innerText = "가죽 표지 덮는 중... 📖";
                    loadingStatusText.innerText = "마법의 고서가 거의 완성되었어요!";
                }

                if (progress === 100) {
                    clearInterval(interval);
                    setTimeout(() => {
                        mainBox.classList.replace('max-w-xl', 'max-w-5xl');
                        initBookData();
                        renderStaticSpread();
                        updateCorners();
                        goToStage('Book');
                    }, 800);
                }
            }, 120);
        }

        function initBookData() {
            // storyLanguage('ko' | 'en')에 따라 실제로 생성되는 동화의 제목과 본문 언어가 달라집니다.
            const isEn = storyLanguage === 'en';

            const title = isEn
                ? `✨ The Legend of Brave ${heroName} ✨`
                : `✨ 용감한 ${heroName}의 전설 ✨`;

            const texts = isEn ? [
                `On a bright, clear day, something magical happened to ${heroName}, who lived in a village deep in the forest. Suddenly, a sparkling little fairy appeared and urgently asked for help.`,
                `The fairy was sad because she had lost the "Starlight Orb" that protected the peace of the forest. The warm-hearted hero decided to help the fairy find it.`,
                `They pushed through a tangle of thorny bushes and entered a deep cave. Surprisingly, a mischievous goblin was in there, playing catch with the Starlight Orb!`,
                `${heroName} cleverly challenged the goblin to a fun riddle and won, safely getting the Starlight Orb back and protecting the peace of the forest.`
            ] : [
                `어느 맑은 날, 깊은 숲속 마을에 사는 ${heroName}에게 아주 신기한 일이 벌어졌어요. 갑자기 반짝이는 꼬마 요정이 나타나 다급하게 도움을 요청했답니다.`,
                `요정은 숲의 평화를 지켜주는 "별빛 구슬"을 잃어버려서 슬퍼하고 있었어요. 마음씨 따뜻한 주인공은 기꺼이 요정을 도와 구슬을 찾기로 결심했죠.`,
                `험난한 가시덤불을 뚫고 깊은 동굴 안으로 들어갔어요. 놀랍게도 그곳에는 장난꾸러기 고블린이 별빛 구슬을 가지고 공놀이를 하고 있었어요!`,
                `${heroName}은(는) 뛰어난 지혜를 발휘해 고블린에게 재미있는 수수께끼를 내어 승리했고, 무사히 별빛 구슬을 돌려받아 숲의 평화를 지켰답니다.`
            ];

            spreads = [
                {
                    left: { type: 'empty' },
                    right: { type: 'cover', title: title, img: 'https://placehold.co/400x500/1a1209/d4a373?text=Legendary+Cover' }
                },
                {
                    left: { type: 'text', text: texts[0] },
                    right: { type: 'image', img: 'https://placehold.co/400x500/e6d8ba/5c4033?text=Magic+Fairy' }
                },
                {
                    left: { type: 'text', text: texts[1] },
                    right: { type: 'image', img: 'https://placehold.co/400x500/e6d8ba/5c4033?text=Lost+Orb' }
                },
                {
                    left: { type: 'text', text: texts[2] },
                    right: { type: 'image', img: 'https://placehold.co/400x500/e6d8ba/5c4033?text=Goblin+Cave' }
                },
                {
                    left: { type: 'text', text: texts[3] },
                    right: { type: 'image', img: 'https://placehold.co/400x500/e6d8ba/5c4033?text=Victory' }
                },
                {
                    left: { type: 'backcover' },
                    right: { type: 'empty' }
                }
            ];
            currentSpread = 0;
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
                    <p class="text-[26px] text-[#4a2e15] leading-[2.1] text-justify break-keep px-8 font-medium">
                        ${pageData.text}
                    </p>
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

components.html(HTML_TEMPLATE, height=980, scrolling=True)

# ----------------------------------------------------------------------------
# 책 안의 별점(localStorage)을 몇 초마다 자동으로 확인해서 파일에 동기화
# ----------------------------------------------------------------------------
if _SYNC_AVAILABLE:
    # 2초마다 스크립트를 자동으로 다시 실행시켜, 매번 아래 st_javascript 호출로
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
