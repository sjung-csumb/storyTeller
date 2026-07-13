# streamlit_app.py
# AI 맞춤형 행동 교정 동화 서비스 - Streamlit 프론트엔드 (모험/신비 테마)
#
# 컨셉: 아이가 "미지의 거대한 숲"을 한 걸음씩 더 깊이 들어가며 정보를 입력하고,
# 숲의 가장 깊은 곳에서 "고대의 마법 동화책"을 발견해 펼쳐보는 흐름입니다.
#
# ※ 가독성을 최우선으로: 전체 글자 크기를 키우고, 배경 이미지 위에 옅은 색을 한 겹
#   덮어(wash) 어떤 화면에서도 글자가 잘 보이도록 했습니다. 페이지 회전 애니메이션은
#   가독성/속도를 위해 제거하고 부드러운 페이드인으로 대체했습니다.
#
# 실행 방법:
#   pip install streamlit httpx
#   streamlit run streamlit_app.py
#
# 백엔드 연동:
#   환경변수 BACKEND_URL 이 설정되어 있으면 해당 API(POST {BACKEND_URL}/generate)를 호출해
#   동화를 생성합니다. 백엔드가 없거나 호출에 실패하면 로컬 샘플 동화 생성기로 대체합니다.
#   백엔드가 spreads를 돌려줄 때는 아래 generate_story_local()과 같은 구조
#   ([{"type":"cover","title":...}, {"type":"spread","text":...}, ..., {"type":"backcover"}])
#   를 따르면 됩니다.

import json
import os
import random
import time
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    import httpx
except ImportError:  # httpx가 없어도 로컬 생성 모드로는 동작하도록
    httpx = None

# ----------------------------------------------------------------------------
# 기본 설정
# ----------------------------------------------------------------------------
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api")  # 기본값으로 백엔드 주소 강제 매핑
RATINGS_FILE = Path(__file__).parent / "satisfaction_ratings.json"

st.set_page_config(
    page_title="AI 동화 만들기 - 판타지 에디션",
    page_icon="📖",
    layout="centered",
)

# 이야기 4장면에 대응하는 아이콘/삽화 테마
STORY_BEATS = [
    {"icon": "🧚", "illust_class": "illust-fairy"},    # 요정 등장
    {"icon": "🔮", "illust_class": "illust-orb"},       # 별빛 구슬
    {"icon": "👺", "illust_class": "illust-goblin"},    # 고블린 동굴
    {"icon": "🏆", "illust_class": "illust-victory"},   # 승리
]


# ----------------------------------------------------------------------------
# 숲 배경 SVG 생성 (단계가 깊어질수록 더 어둡고 안개 짙게)
# ----------------------------------------------------------------------------
def _tree_row(y, scale, color, seed):
    rnd = random.Random(seed)
    trees = []
    x = -60
    while x < 960:
        w = rnd.randint(70, 120) * scale
        h = rnd.randint(160, 240) * scale
        trees.append(f'<polygon points="{x + w / 2},{y - h} {x},{y} {x + w},{y}" fill="{color}"/>')
        x += w * rnd.uniform(0.5, 0.8)
    return "".join(trees)


def make_forest_svg(depth):
    """depth: 0(숲 입구, 밝음) ~ 2(숲 깊은 곳, 어둡고 안개 짙음)"""
    sky_top = ["#a9dcff", "#7fb3d9", "#4f7a9e"][depth]
    sky_bot = ["#ffe3b0", "#e8b880", "#8a6142"][depth]
    fog_op = [0.10, 0.24, 0.40][depth]
    tree_far = ["#6a8a70", "#3f5c47", "#212f1d"][depth]
    tree_near = ["#37502f", "#1e2c1a", "#0e130b"][depth]
    firefly_op = [0.0, 0.5, 0.9][depth]

    fireflies = ""
    rnd = random.Random(depth * 11 + 3)
    for _ in range(9):
        fx = rnd.randint(40, 860)
        fy = rnd.randint(260, 470)
        fireflies += (
            f'<circle cx="{fx}" cy="{fy}" r="3.2" fill="#fff2b0" opacity="{firefly_op}"/>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" preserveAspectRatio="xMidYMax slice">
<defs>
<linearGradient id="sky{depth}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="{sky_top}"/>
<stop offset="100%" stop-color="{sky_bot}"/>
</linearGradient>
</defs>
<rect width="900" height="500" fill="url(#sky{depth})"/>
<circle cx="710" cy="95" r="42" fill="#fff6d8" opacity="0.95"/>
<circle cx="710" cy="95" r="68" fill="#fff6d8" opacity="0.16"/>
{_tree_row(400, 1.0, tree_far, depth * 7 + 1)}
{_tree_row(460, 1.35, tree_near, depth * 7 + 2)}
{fireflies}
<rect width="900" height="500" fill="#ffffff" opacity="{fog_op}"/>
</svg>'''
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe="")


FOREST_BG = [make_forest_svg(d) for d in range(3)]

DUNGEON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" preserveAspectRatio="xMidYMax slice">
<defs>
<radialGradient id="cave" cx="50%" cy="35%" r="75%">
<stop offset="0%" stop-color="#4a3218"/>
<stop offset="55%" stop-color="#1c130a"/>
<stop offset="100%" stop-color="#050301"/>
</radialGradient>
</defs>
<rect width="900" height="500" fill="url(#cave)"/>
</svg>'''
DUNGEON_BG = "data:image/svg+xml," + urllib.parse.quote(DUNGEON_SVG, safe="")

# ----------------------------------------------------------------------------
# 공통 스타일
# ----------------------------------------------------------------------------
BASE_CSS = """
<style>
@font-face {
    font-family: 'StoryFont';
    src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/2411-3@1.0/Ownglyph_ParkDaHyun.woff2') format('woff2');
    font-weight: normal;
    font-display: swap;
}
html, body, [class^="st-"], [class*=" st-"], .stMarkdown, p, span, label,
h1, h2, h3, h4, h5, h6, button, input, textarea {
    font-family: 'StoryFont', 'Pretendard', sans-serif !important;
}

/* ---- 전체 글자 크기 확대 (가독성 우선) ---- */
html, body { font-size: 19px !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {
    font-size: 1.3rem !important; font-weight: 800 !important; color:#4a2e15 !important;
}
.stTextInput input, .stTextArea textarea {
    font-size: 1.2rem !important; padding: 0.7rem 0.9rem !important;
}
[data-testid="stRadio"] label p, [data-testid="stRadio"] label span {
    font-size: 1.15rem !important; font-weight: 600 !important;
}
[data-testid="stCaptionContainer"] p, .stCaption p {
    font-size: 1.1rem !important; color:#6b4a28 !important;
}
.stMarkdown p { font-size: 1.15rem !important; }
button p, button div { font-size: 1.2rem !important; font-weight: 800 !important; }
h1 { font-size: 2.3rem !important; }
h2 { font-size: 1.9rem !important; }
h3 { font-size: 1.6rem !important; }

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}
.block-container { animation: fadeInUp 0.55s ease-out; }

/* 항상 밝게 유지되는 "책 카드" (배경이 숲이든 던전이든 안에서는 항상 잘 보이도록) */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
div.stVerticalBlockBorderWrapper {
    background: #fffaf0 !important;
    border: 2px solid #e8cf9e !important;
    border-radius: 22px !important;
    box-shadow: 0 16px 40px rgba(40,25,5,0.35) !important;
}

/* 상단 진행도 뱃지 & 점 */
.stage-badge {
    display:inline-block; font-size:0.75rem; font-weight:800;
    letter-spacing:0.12em; color:#c2760c; text-transform:uppercase;
    background:#fff2d9; padding:4px 12px; border-radius:999px;
    border:1px solid #f3d29a; margin-bottom:10px;
}
.dots { display:flex; gap:7px; margin-bottom:8px; }
.dot { width:9px; height:9px; border-radius:50%; background:#e9dcc3; }
.dot.active { background:#f59e0b; box-shadow:0 0 8px rgba(245,158,11,0.7); }

/* 동화 언어 토글 */
.lang-toggle-wrap { display:flex; justify-content:flex-end; gap:6px; margin-bottom:-6px; }
.lang-btn-active button {
    background:linear-gradient(135deg,#fbbf24,#f59e0b) !important;
    color:#3b2313 !important; border:none !important; font-weight:800 !important;
    box-shadow:0 3px 10px rgba(245,158,11,0.55) !important;
}
.lang-btn-inactive button {
    background:#f6ede0 !important; color:#b09572 !important;
    border:1px solid #e4d2ae !important; font-weight:700 !important;
}

/* 페이지 전환 시 은은한 페이드인 (회전 효과는 제거) */
.flip-next, .flip-prev { animation: fadeInUp 0.4s ease-out both; }

/* 동화 페이지 카드 - 텍스트는 항상 검정 계열로 고정 (가독성 보장) */
.book-page {
    border-radius:18px; padding:30px 24px; min-height:360px; height:100%;
    display:flex; flex-direction:column; justify-content:center;
    align-items:center; text-align:center; position:relative;
    box-sizing:border-box;
}
.page-papyrus {
    background-color:#eddcb5;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.10'/%3E%3C/svg%3E");
    border:3px solid #b89b72;
    box-shadow: inset 0 0 45px rgba(139,90,43,0.28), 0 10px 24px rgba(90,60,20,0.18);
}
.page-leather {
    background-color:#3b2313;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n2'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n2)' opacity='0.18'/%3E%3C/svg%3E");
    border:3px solid #1f1007;
    box-shadow: inset 0 0 35px rgba(0,0,0,0.85), 0 14px 28px rgba(0,0,0,0.55);
}
.page-icon { font-size:2.6rem; margin-bottom:12px; filter:drop-shadow(0 2px 4px rgba(0,0,0,0.25)); }
.page-text { font-size:1.35rem !important; line-height:2.0; color:#1a1208 !important; text-align:justify; font-weight:600; }
.page-title { font-size:1.9rem !important; font-weight:800; color:#e8c25f !important; letter-spacing:0.05em; text-shadow: 0 2px 6px rgba(0,0,0,0.7); line-height:1.5; }
.page-frame { position:absolute; inset:12px; border:1.5px dashed rgba(139,90,43,0.35); border-radius:12px; pointer-events:none; }
.the-end-mark { font-size:2rem !important; font-weight:800; color:#a67c52 !important; letter-spacing:0.06em; margin-bottom:8px; }
.the-end-label { font-size:1.5rem !important; letter-spacing:0.3em; color:#c79a5b !important; font-family: serif !important; }

/* 삽화(우측 페이지) */
.illustration { border-radius:18px; min-height:360px; height:100%; display:flex; flex-direction:column;
    align-items:center; justify-content:center; position:relative; box-sizing:border-box;
    border:3px solid #b89b72; box-shadow: inset 0 0 30px rgba(0,0,0,0.15), 0 10px 24px rgba(90,60,20,0.18);
    overflow:hidden; }
.illustration .illust-icon { font-size:6rem; filter:drop-shadow(0 6px 10px rgba(0,0,0,0.35)); z-index:2; }
.illustration .sparkle { position:absolute; font-size:1.1rem; opacity:0.8; z-index:1; }
.illust-fairy { background: radial-gradient(circle at 30% 20%, #d9f2df 0%, #9fd8ac 55%, #4f8a5f 100%); }
.illust-orb { background: radial-gradient(circle at 70% 25%, #e6d9ff 0%, #a98bdb 55%, #4b3579 100%); }
.illust-goblin { background: radial-gradient(circle at 40% 70%, #cfd9b0 0%, #7a8a52 55%, #2e3a1c 100%); }
.illust-victory { background: radial-gradient(circle at 50% 30%, #fff2c0 0%, #f5c451 55%, #c1861a 100%); }

/* 별점 영역 - 눈에 띄는 카드로 강조 */
.rating-box {
    background: linear-gradient(135deg,#fff3d6,#ffe6b0);
    border: 2px dashed #e0a838; border-radius: 18px;
    padding: 18px 12px 10px 12px; margin: 6px 0 14px 0;
    text-align:center;
}
.rating-title { text-align:center; font-size:1.3rem !important; font-weight:800; color:#8b5a2b; margin-bottom:10px; }
/* Streamlit이 key값을 클래스로 노출하는 최신 버전을 활용해 별점 버튼만 크게 강조 */
[class*="st-key-star_"] button {
    font-size: 2.6rem !important; line-height:1 !important;
    background: #ffffff !important; border: 2.5px solid #e8cf9e !important;
    border-radius: 14px !important; padding: 10px 0 !important;
    box-shadow: 0 3px 8px rgba(139,90,43,0.15) !important;
}
[class*="st-key-star_"] button:hover {
    border-color:#f59e0b !important; background:#fff7e6 !important;
}
</style>
"""


def stage_bg_css(image_data_uri, wash="rgba(255,250,240,0.78)"):
    # 배경 그림 위에 옅은 색을 한 겹 덮어서(wash) 카드 밖 텍스트까지도 항상 잘 읽히게 합니다.
    return f"""
    <style>
    .stApp {{
        background-image: linear-gradient({wash}, {wash}), url("{image_data_uri}") !important;
        background-size: cover !important;
        background-attachment: fixed !important;
        background-position: center !important;
    }}
    </style>
    """


st.markdown(BASE_CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# 세션 상태 초기화
# ----------------------------------------------------------------------------
def init_state():
    defaults = {
        "session_id": str(uuid.uuid4()),
        "stage": 1,  # 1, 2, 3, "loading", "book"
        "hero_name": "",
        "age": "5",
        "gender": "선택 안함",
        "appearance": "",
        "personality": "",
        "place": "",
        "era": "",
        "mood": "",
        "problem": "",
        "language": "ko",  # "ko" | "en"
        "spreads": [],
        "page_idx": 0,
        "rating": 0,
        "flip_dir": "next",  # 마지막으로 넘긴 방향 ("next"/"prev") - 넘김 애니메이션에 사용
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# 단계별 배경: STAGE1~3 = 숲 입구 -> 깊은 숲 (점점 어두워짐) / 로딩·동화책 = 고대의 동굴(던전)
_STAGE_FOREST_DEPTH = {1: 0, 2: 1, 3: 2}
if st.session_state.stage in _STAGE_FOREST_DEPTH:
    st.markdown(
        stage_bg_css(FOREST_BG[_STAGE_FOREST_DEPTH[st.session_state.stage]], wash="rgba(255,250,240,0.80)"),
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        stage_bg_css(DUNGEON_BG, wash="rgba(255,247,230,0.18)"),
        unsafe_allow_html=True,
    )


def go_to_stage(stage):
    st.session_state.stage = stage


def restart():
    keep_session_id = st.session_state.session_id
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    init_state()
    st.session_state.session_id = keep_session_id


# ----------------------------------------------------------------------------
# 동화 생성 (백엔드 호출 -> 실패 시 로컬 샘플로 대체)
# ----------------------------------------------------------------------------
def generate_story_local(hero_name, language, problem):
    is_en = language == "en"
    title = (
        f"✨ The Legend of Brave {hero_name} ✨"
        if is_en
        else f"✨ 용감한 {hero_name}의 전설 ✨"
    )
    if is_en:
        texts = [
            f"On a bright, clear day, something magical happened to {hero_name}, "
            f"who lived in a village deep in the forest. Suddenly, a sparkling "
            f"little fairy appeared and urgently asked for help.",
            "The fairy was sad because she had lost the \"Starlight Orb\" that "
            "protected the peace of the forest. The warm-hearted hero decided to "
            "help the fairy find it.",
            "They pushed through a tangle of thorny bushes and entered a deep "
            "cave. Surprisingly, a mischievous goblin was in there, playing "
            "catch with the Starlight Orb!",
            f"{hero_name} cleverly challenged the goblin to a fun riddle and "
            f"won, safely getting the Starlight Orb back and protecting the "
            f"peace of the forest. And about the problem they faced ("
            f"{problem or 'a small worry'}) — with newfound courage, "
            f"{hero_name} was able to face it too.",
        ]
    else:
        texts = [
            f"어느 맑은 날, 깊은 숲속 마을에 사는 {hero_name}에게 아주 신기한 일이 "
            f"벌어졌어요. 갑자기 반짝이는 꼬마 요정이 나타나 다급하게 도움을 "
            f"요청했답니다.",
            "요정은 숲의 평화를 지켜주는 \"별빛 구슬\"을 잃어버려서 슬퍼하고 "
            "있었어요. 마음씨 따뜻한 주인공은 기꺼이 요정을 도와 구슬을 찾기로 "
            "결심했죠.",
            "험난한 가시덤불을 뚫고 깊은 동굴 안으로 들어갔어요. 놀랍게도 그곳에는 "
            "장난꾸러기 고블린이 별빛 구슬을 가지고 공놀이를 하고 있었어요!",
            f"{hero_name}은(는) 뛰어난 지혜를 발휘해 고블린에게 재미있는 수수께끼를 "
            f"내어 승리했고, 무사히 별빛 구슬을 돌려받아 숲의 평화를 지켰답니다. "
            f"그리고 {hero_name}을(를) 괴롭히던 고민({problem or '작은 걱정거리'})도 "
            f"이 모험에서 얻은 용기 덕분에 씩씩하게 이겨낼 수 있었어요.",
        ]

    spreads = [{"type": "cover", "title": title}]
    for t in texts:
        spreads.append({"type": "spread", "text": t})
    spreads.append({"type": "backcover"})
    return spreads


def generate_story(payload):
    """백엔드가 설정되어 있으면 호출하고, 실패하면 에러를 냅니다."""
    if BACKEND_URL and httpx is not None:
        try:
            # 프론트엔드의 Payload를 백엔드 스펙으로 매핑
            backend_payload = {
                "appearance": payload.get("appearance", "귀여움"),
                "personality": payload.get("personality", "활발함"),
                "place": payload.get("place", "숲속"),
                "time_period": payload.get("era", "아주 먼 옛날"),
                "mood": payload.get("mood", "신비로움"),
                "problem_situation": payload.get("problem", "작은 걱정거리"),
                "language": payload.get("language", "ko"),
            }
            
            # 동화와 이미지 5장을 모두 그릴 때까지 타임아웃 120초 대기
            resp = httpx.post(f"{BACKEND_URL}/children/1/fairytales", json=backend_payload, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
            
            content_list = json.loads(data.get("content_json", "[]"))
            spreads = []
            
            if content_list and content_list[0].get("is_cover"):
                cover = content_list.pop(0)
                spreads.append({"type": "cover", "title": data.get("title", "동화책"), "image_url": cover.get("image_url")})
            else:
                spreads.append({"type": "cover", "title": data.get("title", "동화책")})
                
            for page in content_list:
                spreads.append({"type": "spread", "text": page.get("text", ""), "image_url": page.get("image_url")})
                
            spreads.append({"type": "backcover"})
            return spreads
        except Exception as e:
            st.error(f"백엔드 연결에 실패했습니다: {e}")
            raise e

    st.error("BACKEND_URL 이나 httpx 모듈이 없습니다.")
    return []


# ----------------------------------------------------------------------------
# 만족도 별점 저장 (파일 기반 - localStorage 대체)
# ----------------------------------------------------------------------------
def save_rating(rating):
    record = {
        "session_id": st.session_state.session_id,
        "hero_name": st.session_state.hero_name,
        "language": st.session_state.language,
        "rating": rating,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
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


def stage_dots(active_idx):
    dots = ""
    for i in range(3):
        cls = "dot active" if i == active_idx else "dot"
        dots += f'<span class="{cls}"></span>'
    st.markdown(f'<div class="dots">{dots}</div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Stage 1 : 주인공 이름 / 나이 / 성별
# ----------------------------------------------------------------------------
def render_stage1():
    with st.container(border=True):
        stage_dots(0)
        st.markdown('<span class="stage-badge">STAGE 1 / 3 · 숲의 입구</span>', unsafe_allow_html=True)
        st.title("📖 AI 동화만들기 프로젝트")
        st.caption("🧭 이야기의 주인공을 설정해 주세요")

        with st.form("stage1_form"):
            hero_name = st.text_input(
                "🦸 주인공 이름", value=st.session_state.hero_name, placeholder="예: 김사과"
            )
            age = st.radio(
                "🎂 나이", ["3세", "4세", "5세", "6세"],
                index=["3", "4", "5", "6"].index(st.session_state.age),
                horizontal=True,
            )
            gender = st.radio(
                "⚧ 성별", ["선택 안함", "남", "여"],
                index=["선택 안함", "남", "여"].index(st.session_state.gender),
                horizontal=True,
            )
            submitted = st.form_submit_button(
                "숲 속으로 한 걸음 ➜", use_container_width=True, type="primary"
            )

    if submitted:
        if not hero_name.strip():
            st.error("주인공 이름을 입력해 주세요.")
        else:
            st.session_state.hero_name = hero_name.strip()
            st.session_state.age = age.replace("세", "")
            st.session_state.gender = gender
            go_to_stage(2)
            st.rerun()


# ----------------------------------------------------------------------------
# Stage 2 : 외형 / 성격 / 장소 / 시대 / 분위기
# ----------------------------------------------------------------------------
def render_stage2():
    with st.container(border=True):
        stage_dots(1)
        st.markdown('<span class="stage-badge">STAGE 2 / 3 · 숲의 중턱</span>', unsafe_allow_html=True)
        st.header("🗺️ 어떤 이야기인가요?")
        st.caption("주인공과 배경에 대해 더 자세히 알려주세요")

        with st.form("stage2_form"):
            appearance = st.text_input(
                "👗 주인공의 외형", value=st.session_state.appearance,
                placeholder="예: 빨간 모자를 쓰고 있어요",
            )
            personality = st.text_input(
                "💫 주인공의 성격", value=st.session_state.personality,
                placeholder="예: 호기심이 많고 용감해요",
            )
            col1, col2 = st.columns(2)
            with col1:
                place = st.text_input(
                    "🏞️ 장소", value=st.session_state.place, placeholder="예: 깊은 숲속"
                )
            with col2:
                era = st.text_input(
                    "⏳ 시대", value=st.session_state.era, placeholder="예: 아주 먼 옛날"
                )
            mood = st.text_input(
                "🌙 분위기", value=st.session_state.mood,
                placeholder="예: 신비롭고 따뜻한 느낌",
            )

            c1, c2 = st.columns([1, 2])
            prev_clicked = c1.form_submit_button("이전", use_container_width=True)
            next_clicked = c2.form_submit_button(
                "더 깊은 곳으로 ➜", use_container_width=True, type="primary"
            )

    if prev_clicked:
        go_to_stage(1)
        st.rerun()

    if next_clicked:
        if not all([appearance.strip(), personality.strip(), place.strip(), era.strip(), mood.strip()]):
            st.error("모든 항목을 입력해 주세요.")
        else:
            st.session_state.appearance = appearance.strip()
            st.session_state.personality = personality.strip()
            st.session_state.place = place.strip()
            st.session_state.era = era.strip()
            st.session_state.mood = mood.strip()
            go_to_stage(3)
            st.rerun()


# ----------------------------------------------------------------------------
# Stage 3 : 문제 상황 + 동화 언어(KO/EN) 선택
# ----------------------------------------------------------------------------
def render_stage3():
    with st.container(border=True):
        top_l, top_r = st.columns([3, 1])
        with top_r:
            st.markdown('<div class="lang-toggle-wrap">', unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                st.markdown(
                    f'<div class="{"lang-btn-active" if st.session_state.language == "ko" else "lang-btn-inactive"}">',
                    unsafe_allow_html=True,
                )
                if st.button("KO", key="lang_ko_btn", use_container_width=True):
                    st.session_state.language = "ko"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with b2:
                st.markdown(
                    f'<div class="{"lang-btn-active" if st.session_state.language == "en" else "lang-btn-inactive"}">',
                    unsafe_allow_html=True,
                )
                if st.button("EN", key="lang_en_btn", use_container_width=True):
                    st.session_state.language = "en"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with top_l:
            stage_dots(2)
            st.markdown('<span class="stage-badge">STAGE 3 / 3 · 고대의 서고 앞</span>', unsafe_allow_html=True)
            st.header("⚡ 어떤 일이 생겼나요?")
            lang_label = "한국어" if st.session_state.language == "ko" else "English"
            st.caption(f"주인공이 겪는 문제나 사건을 적어주세요 · 생성될 동화 언어: **{lang_label}**")

        with st.form("stage3_form"):
            problem = st.text_area(
                "🌩️ 문제 상황",
                value=st.session_state.problem,
                height=180,
                placeholder=(
                    "예: 소중한 장난감을 잃어버려서 슬퍼하고 있어요. "
                    "친구들과 어떻게 화해해야 할지 모르겠어요."
                ),
            )
            c1, c2 = st.columns([1, 2])
            prev_clicked = c1.form_submit_button("이전", use_container_width=True)
            submit_clicked = c2.form_submit_button(
                "✨ 이야기 만들기!", use_container_width=True, type="primary"
            )

    if prev_clicked:
        go_to_stage(2)
        st.rerun()

    if submit_clicked:
        if not problem.strip():
            st.error("문제 상황을 입력해 주세요.")
        else:
            st.session_state.problem = problem.strip()
            go_to_stage("loading")
            st.rerun()


# ----------------------------------------------------------------------------
# 로딩 (진행률 표시 + 동화 생성 호출)
# ----------------------------------------------------------------------------
def render_loading():
    with st.container(border=True):
        st.markdown(
            '<div style="text-align:center;font-size:3rem;">🪄</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<h3 style="text-align:center;">마법의 책을 엮는 중...</h3>',
            unsafe_allow_html=True,
        )
        status = st.empty()
        bar = st.progress(0)

        payload = {
            "session_id": st.session_state.session_id,
            "hero_name": st.session_state.hero_name,
            "age": st.session_state.age,
            "gender": st.session_state.gender,
            "appearance": st.session_state.appearance,
            "personality": st.session_state.personality,
            "place": st.session_state.place,
            "era": st.session_state.era,
            "mood": st.session_state.mood,
            "problem": st.session_state.problem,
            "language": st.session_state.language,
        }

        progress = 0
        phases = [
            (0, "🪄 주문 외우는 중..."),
            (30, "🖋️ 고대의 마법 잉크 섞는 중..."),
            (70, "📖 가죽 표지 덮는 중..."),
        ]
        while progress < 100:
            progress = min(100, progress + 12)
            bar.progress(progress)
            phase_text = phases[0][1]
            for threshold, text in phases:
                if progress >= threshold:
                    phase_text = text
            status.markdown(
                f'<p style="text-align:center;">{phase_text} &nbsp; <b>{progress}%</b></p>',
                unsafe_allow_html=True,
            )
            time.sleep(0.12)

    spreads = generate_story(payload)
    st.session_state.spreads = spreads
    st.session_state.page_idx = 0
    go_to_stage("book")
    st.rerun()


# ----------------------------------------------------------------------------
# 완성된 동화책 (좌: 글 / 우: 삽화 두쪽 스프레드 + 만족도 별점)
# ----------------------------------------------------------------------------
def _flip_class():
    return "flip-next" if st.session_state.flip_dir == "next" else "flip-prev"


def render_illustration(beat):
    sparkles = '<span class="sparkle" style="top:12%;left:14%;">✦</span>' \
               '<span class="sparkle" style="top:20%;right:16%;">✧</span>' \
               '<span class="sparkle" style="bottom:16%;left:20%;">✦</span>'
    st.markdown(
        f'<div class="illustration {beat["illust_class"]} {_flip_class()}">'
        f"{sparkles}"
        f'<div class="illust-icon">{beat["icon"]}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_page(page, story_idx):
    flip = _flip_class()
    if page["type"] == "cover":
        bg_image = f"background-image: url('http://127.0.0.1:8000{page['image_url']}'); background-size: cover;" if page.get("image_url") else ""
        st.markdown(
            f'<div class="book-page page-leather {flip}" style="{bg_image}">'
            f'<div class="page-frame" style="background: rgba(255,255,255,0.6);"></div>'
            f'<div class="page-icon">🏰</div>'
            f'<div class="page-title" style="color: #000; text-shadow: 2px 2px 4px #fff;">{page.get("title", "")}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    elif page["type"] == "backcover":
        end_mark = (
            "" if st.session_state.language == "en"
            else '<div class="the-end-mark">끝</div>'
        )
        st.markdown(
            f'<div class="book-page page-leather {flip}">'
            f'<div class="page-frame"></div>'
            f'<div class="page-icon">🌟</div>'
            f"{end_mark}"
            f'<div class="the-end-label">THE END</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:  # "spread" - 좌: 텍스트 / 우: 삽화
        beat = STORY_BEATS[story_idx % len(STORY_BEATS)]
        left, right = st.columns(2)
        with left:
            st.markdown(
                f'<div class="book-page page-papyrus {flip}">'
                f'<div class="page-frame"></div>'
                f'<div class="page-icon">{beat["icon"]}</div>'
                f'<p class="page-text">{page["text"]}</p>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with right:
            if page.get("image_url"):
                st.image(f"http://127.0.0.1:8000{page['image_url']}", use_container_width=True)
            else:
                render_illustration(beat)


def render_star_rating():
    st.markdown('<div class="rating-box">', unsafe_allow_html=True)
    st.markdown(
        '<p class="rating-title">🌟 이야기가 마음에 드셨나요? 아래 별을 눌러 평가해 주세요! 🌟</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for i, col in enumerate(cols, start=1):
        filled = "⭐" if i <= st.session_state.rating else "☆"
        with col:
            if st.button(filled, key=f"star_{i}", use_container_width=True):
                st.session_state.rating = 0 if st.session_state.rating == i else i
                save_rating(st.session_state.rating)
                st.rerun()

    if st.session_state.rating > 0:
        st.success(f"{st.session_state.rating}점으로 저장되었습니다 ✅")
    else:
        st.caption("👆 별을 눌러 0~5점으로 평가해 주세요 (같은 별을 다시 누르면 취소돼요)")
    st.markdown("</div>", unsafe_allow_html=True)


def render_book():
    st.markdown(
        '<h4 style="text-align:center;color:#f3e3c3;">✨ 고대의 마법 동화책 ✨</h4>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        spreads = st.session_state.spreads
        idx = st.session_state.page_idx
        total = len(spreads)

        # cover(0) / backcover(마지막) 를 제외한 순번을 삽화 매핑에 사용
        story_idx = max(0, idx - 1)
        render_page(spreads[idx], story_idx)
        st.markdown(
            f'<p style="text-align:center;opacity:0.7;">📄 {idx + 1} / {total} 페이지</p>',
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("◀ 이전", disabled=idx == 0, use_container_width=True):
                st.session_state.flip_dir = "prev"
                st.session_state.page_idx -= 1
                st.rerun()
        with c3:
            if st.button("다음 ▶", disabled=idx == total - 1, use_container_width=True):
                st.session_state.flip_dir = "next"
                st.session_state.page_idx += 1
                st.rerun()

        if idx == total - 1:
            st.divider()
            render_star_rating()
            st.divider()
            if st.button(
                "처음부터 다시 만들기 🔄", use_container_width=True, type="primary"
            ):
                restart()
                st.rerun()


# ----------------------------------------------------------------------------
# 라우팅
# ----------------------------------------------------------------------------
stage = st.session_state.stage
if stage == 1:
    render_stage1()
elif stage == 2:
    render_stage2()
elif stage == 3:
    render_stage3()
elif stage == "loading":
    render_loading()
elif stage == "book":
    render_book()
