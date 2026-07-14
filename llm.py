import os
import re
import json
import asyncio
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, START, END

from models import Child
from kb_retriever import get_retriever

load_dotenv()

UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY")

client = OpenAI(
    api_key=UPSTAGE_API_KEY,
    base_url="https://api.upstage.ai/v1/solar"
)

def generate_fairy_tale(
    child: Child,
    appearance: str,
    personality: str,
    place: str,
    time_period: str,
    mood: str,
    problem_situation: str
) -> dict:
    if not UPSTAGE_API_KEY:
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (API 키 없음)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False)
        }

    system_prompt = (
        "너는 아동 심리 발달과 행동교정을 돕는 전문 동화 작가야. "
        "주어진 아이의 성향과 교정해야 할 문제 상황을 바탕으로 짧고 교훈적이면서 재미있는 동화를 작성해줘. "
        "**가장 중요한 규칙: 동화는 반드시 기-승-전-결 구조를 갖춘 딱 4페이지로만 구성해야 해.**"
    )
    
    user_prompt = (
        f"주인공 이름: {child.name}\n나이: {child.age}세\n성별: {child.gender}\n"
        f"주인공 외형: {appearance}\n주인공 성격: {personality}\n배경 장소: {place}\n"
        f"배경 시대: {time_period}\n동화 분위: {mood}\n교정이 필요한 문제 상황: {problem_situation}\n"
        "\n출력 형식은 반드시 순수한 JSON 형태여야 하며...\n(생략)"
    )

    try:
        response = client.chat.completions.create(
            model="solar-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        result_str = response.choices[0].message.content.strip()
        start_idx = result_str.find('{')
        end_idx = result_str.rfind('}')
        if start_idx != -1 and end_idx != -1:
            result_str = result_str[start_idx:end_idx+1]
            
        result_json = json.loads(result_str)
        return {
            "title": result_json.get("title", f"{child.name}의 모험"),
            "cover_image_prompt": result_json.get("cover_image_prompt", "A beautiful storybook cover art"),
            "content_json": json.dumps(result_json.get("content", [{"page": 1, "text": result_str}]), ensure_ascii=False)
        }
    except Exception as e:
        print(f"LLM API Error: {e}")
        return {
            "title": f"{child.name}의 모험 (생성 실패)",
            "cover_image_prompt": "A beautiful storybook cover art",
            "content_json": json.dumps([{"page": 1, "text": "동화 생성 오류"}], ensure_ascii=False)
        }


# =========================================================================
# 2. LangGraph 기반 Multi-Agent RAG 로직
# =========================================================================

# 스키마 정의
class StoryPage(BaseModel):
    page: int = Field(description="페이지 번호 (1~4)")
    text: str = Field(description="한국어 원본 텍스트")
    text_en: str = Field(description="영어 번역 텍스트")
    image_prompt: str = Field(description="이 페이지를 위한 영문 DALL-E 이미지 프롬프트")

class StoryFormat(BaseModel):
    title: str = Field(description="동화의 제목")
    cover_image_prompt: str = Field(description="동화책 표지를 위한 영문 이미지 프롬프트")
    content: List[StoryPage] = Field(description="각 페이지 정보 배열")

class GraphState(TypedDict):
    child_info: Dict[str, Any]
    language: str
    rag_context: str
    guide_text: str
    draft_ko: str
    feedback: Optional[str]
    revision_count: int
    final_json: str

# 랭체인 업스테이지 최신 모델
draft_llm = ChatOpenAI(model="solar-pro3", base_url="https://api.upstage.ai/v1/solar", api_key=UPSTAGE_API_KEY)
finalize_llm = ChatOpenAI(model="solar-pro2", base_url="https://api.upstage.ai/v1/solar", api_key=UPSTAGE_API_KEY)

# 항상 금지: 공포심을 동기로 삼는 표현 (문맥과 무관하게 위험)
FEAR_PHRASES = ["무서워서", "무섭", "화내는 게", "화낼까"]

# 조건부 금지: '실망/슬프/속상' 자체는 아이 자신의 감정을 공감해주는 좋은 표현으로도 쓰이므로
# (예: "너 오늘 속상했겠다") 무조건 막지 않는다. 대신 그 감정을 엄마/아빠/선생님 같은 '어른'이
# 느꼈다고 아이 탓으로 돌리는 문장(예: "네가 그래서 엄마도 슬펐단다")일 때만 금지한다.
GUILT_EMOTION_WORDS = r"(실망|슬펐|슬프|속상|마음이\s*아프)"
ADULT_REF = r"(엄마|아빠|선생님)"
GUILT_PATTERN_RE = re.compile(
    rf"{ADULT_REF}[^.!?]{{0,20}}{GUILT_EMOTION_WORDS}"
    rf"|{GUILT_EMOTION_WORDS}[^.!?]{{0,20}}{ADULT_REF}"
    rf"|때문에[^.!?]{{0,20}}{GUILT_EMOTION_WORDS}"
    rf"|{GUILT_EMOTION_WORDS}[^.!?]{{0,20}}때문에"
)

PAGE_MARKER_RE = re.compile(r"\[\s*(\d+)\s*페이지\s*\]")


def split_story_pages(text: str) -> List[str]:
    """draft_node가 만든 '[1페이지] ... [2페이지] ...' 형식의 원문을
    페이지별 텍스트 리스트로 나눈다. LLM이 다시 타이핑하지 않고
    이 함수로 나눈 원문 그대로를 최종 JSON에 넣기 위한 용도."""
    if not text:
        return []
    matches = list(PAGE_MARKER_RE.finditer(text))
    if not matches:
        return []
    pages = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append(text[start:end].strip())
    return pages


MAX_SENTENCES_PER_PAGE = 4
SENTENCE_END_RE = re.compile(r"[.!?]+[)'\"]*")


def count_sentences(page_text: str) -> int:
    """마침표/물음표/느낌표 개수로 문장 수를 대략 센다.
    완벽한 문장 분리기는 아니지만, '문장이 너무 많다'를 걸러내는 용도로는 충분하다."""
    if not page_text:
        return 0
    return len(SENTENCE_END_RE.findall(page_text))


# --- Nodes ---

def retrieve_node(state: GraphState) -> GraphState:
    child = state["child_info"]
    problem = child.get("problem_situation", "")
    
    retriever = get_retriever()
    # 전문가 지침: '문제행동/성향'으로 검색 (해결 원칙을 찾기 위함)
    query = f"아이의 문제 행동: {problem}\n아이의 성향: {child.get('personality')}\n"
    few_shot_results = retriever.retrieve_few_shot(query, top_k=1)
    # 모범 동화 예시: '대상 연령/분위기'로 검색 (문체·분량 스타일 참고가 목적)
    example_query = f"대상 연령 {child.get('age')}세 / 분위기 {child.get('mood')}"
    example_results = retriever.retrieve_example(example_query, top_k=1)
    
    rag_context = ""
    guide_text = ""
    if few_shot_results:
        raw_guide = few_shot_results[0]
        rag_context += (
            f"--- [보건복지부 아동 심리 전문가 지침] ---\n{raw_guide}\n\n"
            "위 지침에서 '왜 이 대안 행동이 효과적인지'라는 심리학적 원칙(예: 신체 에너지 발산, 스스로 진정하기, "
            "선택지를 주기)만 참고해. 지침에 나온 구체적인 소품이나 활동(예: 샌드백, 블록, 크레파스 등)을 "
            "그대로 이야기에 옮겨 적지 마. 대신 그 원칙을, 지금 이 이야기의 배경/소재(장소, 문제 상황, 등장 사물)를 "
            "그대로 활용한 새로운 대안 행동으로 재창작해. "
            "예를 들어 원칙이 '신체 에너지를 발산하게 하라'이고 이야기 배경이 축구장이라면, "
            "'샌드백을 치게 한다'가 아니라 '공을 힘껏 차보게 한다'처럼 이야기 세계관 안에서 해결하도록 써.\n\n"
        )
        summary_prompt = (
            "다음은 아동 심리 전문가의 육아 지침입니다. "
            "이 내용을 부모님들이 읽고 바로 따라해볼 수 있도록, 다정하고 친절한 어투(~해보세요, ~좋아요)로 4~5줄의 짧은 '육아 팁'으로 요약해주세요. "
            "마크다운이나 특수기호 없이 자연스러운 순수 텍스트로만 작성하세요.\n\n"
            f"[원본 지침]\n{raw_guide}"
        )
        try:
            guide_resp = draft_llm.invoke([HumanMessage(content=summary_prompt)])
            guide_text = guide_resp.content.strip()
        except Exception:
            guide_text = "아이의 마음을 먼저 공감해주고, 긍정적인 대안 행동을 함께 찾아보세요."
        
    if example_results:
        rag_context += (
            f"--- [모범 동화 예시 (문체/분량 참고용)] ---\n{example_results[0]}\n\n"
            "위 예시에서는 오직 '문체·어투·문장 길이·호흡·구어체 느낌'만 참고해. "
            "예시의 플롯, 등장인물, 소재, 배경, 사건은 절대 가져다 쓰지 마. "
            "이야기 내용은 이번 입력(주인공/문제 상황/배경)에 맞춰 완전히 새로 창작하고, "
            "출력은 반드시 [1페이지]~[4페이지] 4개 단락의 순수 텍스트로만 작성해.\n"
        )
        
    return {"rag_context": rag_context, "guide_text": guide_text, "revision_count": 0}

def draft_node(state: GraphState) -> GraphState:
    child = state["child_info"]
    age = child.get("age", 4)
    gender = child.get("gender", "무관")
    name = child.get("name", "아이")
    

    onomatopoeia_pool = (
        "폴짝폴짝, 두근두근, 뽀득뽀득, 살금살금, 반짝반짝, 쿵쾅쿵쾅, 데굴데굴, 방긋방긋, 사르르, 몽글몽글, "
        "사각사각(과자를 씹거나 낙엽을 밟는 등 '바스락거리는 소리'에만), 두리번두리번, 씩씩하게"
    )
    onomatopoeia_note = (
        f"위 목록에서 이번 장면에 실제로 어울리는 것만 골라 페이지마다 1~2개 자연스럽게 녹여내. "
        "청각과 무관한 대상(햇살, 색깔, 감정 등)에 소리를 나타내는 의성어를 억지로 붙이지 마. "
        "같은 단어를 이야기 전체에서 두 번 이상 반복하지 마."
    )

    if age <= 3:
        vocab_rule = (
            f"입력된 {age}세 아동의 인지 수준에 맞춰 '포탈' 대신 '비밀 문' 등 아주 쉽고 직관적인 단어를 써. "
            f"{onomatopoeia_note} (참고 목록: {onomatopoeia_pool}) "
            "특히 배경이나 문맥에서 '유치원'이라는 단어는 절대 쓰지 말고 무조건 '어린이집'으로 고정해."
        )
    elif age == 4:
        vocab_rule = (
            f"입력된 {age}세 아동의 인지 수준에 맞춰 '포탈' 대신 '비밀 문' 등 아주 쉽고 직관적인 단어를 써. "
            f"{onomatopoeia_note} (참고 목록: {onomatopoeia_pool})"
        )
    else:
        vocab_rule = (
            f"입력된 {age}세 아동의 어휘 수준에 맞춘 단어와 문장 구조를 사용해. 동화가 너무 유치해지지 않도록 "
            f"페이지당 의성어/의태어는 0~1개만 자연스럽게. {onomatopoeia_note} (참고 목록: {onomatopoeia_pool})"
        )
    jargon_rule = (
        "'골을 먹다', '실점하다' 같은 스포츠·전문 용어나 '불편해', '곤란해' 같은 어른스러운 어휘는 쓰지 말고, "
        "아이가 실제로 쓸 법한 쉬운 말(예: '하지 마!', '아파!', '싫어!')로 풀어써. "
        "'그', '그녀' 같은 격식체 대명사 대신 주인공 이름을 반복해서 불러."
    )
    length_rule = "아동이 읽기 편하도록 1쪽은 자유롭게 작성하되, 2쪽, 3쪽, 4쪽의 텍스트는 각각 '최대 4문장'을 넘기지 마. 내용에 따라 2~4문장 사이에서 자연스럽게 끊고, 문장 수를 채우려고 어색하게 늘리거나 억지로 압축하지 마."
    resolution_rule = "조력자(부모, 코치, 선생님 등)의 따뜻한 스킨십이나 '어떻게 하면 좋을까?'라는 질문을 통해 아이 스스로 대안을 찾고 안정을 얻도록 유도해."

    lang_val = state.get("language", "ko").lower()
    if lang_val == "en":
        lang_rule = "미국의 양육자와 아이가 일상에서 쓰는 다정하고 자연스러운 구어체를 사용해. **반드시 이야기 전체 텍스트를 영문(English)으로 작성해!**"
    else:
        lang_rule = "한국의 양육자와 아이가 일상에서 쓰는 다정하고 자연스러운 구어체(~해요, ~했어요)를 사용해. **반드시 이야기 전체 텍스트를 순수 한국어(한글)로만 작성하며, 한자(예: 今天)나 다른 외국어 혼용을 절대 금지해!**"

    if gender == "남자":
        gender_rule = "스토리에 모험심을 자극하고 활동적인 전개(탐험, 문제 해결 등)를 살짝 섞어주면 좋아."
    elif gender == "여자":
        gender_rule = "풍부한 감수성을 자극하고 판타지적 요소(마법, 요정 등)를 살짝 섞어주면 좋아."
    else:
        gender_rule = "아이의 성향에 맞추어 전개해."

    system_prompt = (
    "너는 아동 심리 발달을 돕는 다정하고 창의적인 영유아 맞춤형 구연동화 작가야.\n"
    f"주인공 이름은 무조건 '{name}'(으)로 고정하며, 기계적인 번역투를 배제하고 입에 착 붙는 다정한 구연동화 어투를 사용해줘.\n\n"

    "🚨 [출력 포맷 및 분량 제한 (초강력 규칙)]\n"
    "1. 오직 동화 텍스트만 출력하고, 이야기 끝에 '육아 가이드', '해설', '사족'을 절대 생성하지 마.\n"
    "2. 반드시 [1페이지], [2페이지], [3페이지], [4페이지] 딱 4개의 단락으로만 구성해. ('쪽' 표기 절대 금지)\n"
    "3. 문장 부호 및 따옴표: 모든 문장은 문장 부호(., ?, !)로 완벽히 끝내고, 쌍따옴표(\")는 절대 금지해. 대화는 무조건 작은따옴표(')만 사용해.\n\n"

    "💡 [맞춤형 어투 및 분량 가이드]\n"
    f"- 언어/문체: {lang_rule} | 어휘/연령: {vocab_rule} | 금지어휘: {jargon_rule} | 성향: {gender_rule} | 분량: {length_rule}\n"
    f"- 조사 일치 규칙: '{name}' 뒤에 붙는 조사(는/은, 가/이)는 1페이지에서 맨 처음 사용한 형태를 4페이지 끝까지 완벽하게 동일하게 유지해.\n\n"

    "💡 [부모 입력값 전처리 규칙]\n"
    "- [실망/슬픔] 요구 시: 부모의 부정적 감정 대신 '행동을 안 했을 때 아이가 현실에서 겪을 실제적 불편함이나 결과'로 치환할 것.\n"
    "- [거짓말/교정] 요구 시: 잘못을 추궁(~했지?)하거나 징벌하지 말고, '솔직하게 말했을 때 얻는 용기와 칭찬'으로 유도할 것.\n\n"

    "📖 [기승전결 4페이지 서사 가이드 및 인과관계]\n"
    "각 페이지는 앞 문장의 원인이 뒷 문장의 결과로 이어지는 강력한 인과관계를 유지해야 해.\n\n"
    
    "[1페이지] 배경 소개와 일상\n"
    "- 입력된 [배경(장소)]을 메인 무대로 삼아, 주인공의 즐거운 일상을 묘사하되 이야기의 중심이 될 '단 하나의 핵심 소재(장난감, 반찬, 물건 등)'를 자연스럽게 등장시킬 것.\n"
    "- 억지 설정 주의: 식사 시간, 양치 시간 등 특정 상황에 맞지 않게 억지로 장난감 놀이를 끼워 넣지 마 (예: 식탁에서 장난감 블록을 먹으려 하는 등의 부자연스러운 서사 금지).\n"
    "- 꼼수 방지: 3페이지 솔루션을 편하게 하려고 처음부터 '여분의 장난감이나 물건이 있었다'는 식으로 소재를 임의로 늘리지 마.\n\n"
    
    "[2페이지] 미숙한 충동으로 인한 문제 행동 발생\n"
    "- 악의가 아니라 '서툰 감정 표현과 충동' 때문에 주어진 [문제 상황](예: 때리기, 안 먹기, 떼쓰기 등)을 여과 없이 저지르는 장면.\n"
    "- 주인공이 가해자이거나 고집을 피우는 시점이어야 하며, 스스로 피해자인 척('아파!') 하거나 이른 반성을 하는 것은 절대 금지.\n"
    "- 인과관계 순서 엄수: [주인공의 문제 행동] → [그 결과 주변(친구, 부모 등)이 곤란해지거나 주인공이 스스로 불편함을 겪는 직접적 피해] → [결국 주인공이 난처해지거나 혼자 남음]의 순서대로 서술할 것.\n\n"
    
    "[3페이지] 조력자의 등장과 3단계 솔루션 및 배경 일치 (★최대 핵심)\n"
    "- 🔗 갈등-해결 소재 일치의 법칙: 1, 2페이지에서 정한 장소·소재를 이야기 끝까지 유지해. 배경과 무관한 소품(갑자기 샌드백/쿠션 등장 등)은 절대 금지하며, 하단에 제공되는 [육아 지침/가이드라인]을 현재 배경의 사물과 상황에 맞게 100% 치환해 솔루션으로 활용할 것.\n"
    "- 👤 조력자 맵핑 우선순위:\n"
    "  - IF 사용자가 입력한 [성향/문제상황]에 특정 캐릭터(공룡, 공주 등)를 직접 명시했다면: 해당 캐릭터를 조언자로 필수 등장시킬 것.\n"
    "  - ELSE (캐릭터 언급이 없다면): 무조건 현재 배경에 맞는 현실 어른인 '엄마', '아빠', '선생님(코치)' 중 한 명을 조력자로 고정할 것.\n"
    "- 🚨 아래 ①, ②, ③ 순서를 생략이나 요약 없이 무조건 본문 구체적 텍스트로 녹여내:\n"
    "  ① 진정 (감정 수용 및 지침 반영): 조력자가 아이의 감정을 부드럽게 읽어주고 100% 수용해 줌. 이때 [육아 지침]에 특정 진정 방식(심호흡 등)이 있다면 이를 따르고, 없다면 따뜻한 포옹이나 쓰다듬기 등으로 자연스럽게 차분해지도록 유도할 것.\n"
    "  ② 전환 (RAG 지침 적극 반영 & 물리 분출 금지): 하단에 제공된 [육아 지침/가이드라인]의 해결책을 바탕으로 2페이지 문제의 원인이 된 '그 상황/사물'을 활용해 긍정적인 행동(예: 놀이로 접근하기, 차례 지키기 등)으로 전환할 것. 단, 물건을 거칠게 다루는 분출 행위나 물건을 하나 더 주어 무마하는 꼼수는 절대 금지.\n"
    "  ③ 소통: 주인공이 마음을 가라앉히고 친구나 주변에 예쁘게 표현함 ('미안해', '같이 하자', '내가 해볼게' 등).\n\n"
    
    "[4페이지] 현실 실천 및 사회적 화합\n"
    "- 🎯 문제 행동 '직접 교정'의 법칙 (필수): 주인공은 반드시 [문제 상황]에서 요구된 바람직한 행동을 스스로 '실제로 해내는' 구체적 장면을 보여줘야 해. "
    "예) 편식이면 채소를 '진짜로 한 입 먹는다', 양치 거부면 '직접 이를 닦는다', 안 나눔이면 '친구에게 나눠 준다', 때리기면 '친구와 사이좋게 함께 논다', 떼쓰기면 '스스로 참고 기다린다'.\n"
    "- 🚫 회피형 결말 절대 금지: 문제의 대상(채소, 장난감, 양치 등)을 치우기·바구니에 담아 없애기·다른 곳(친구 집 등)으로 보내기·나중으로 미루기처럼 '없애거나 피하는' 방식으로 끝내지 마. "
    "주인공이 그 대상과 '직접 긍정적으로 상호작용(먹기, 사용하기, 나눠 쓰기)'하는 장면이 반드시 있어야 해.\n"
    "- 주인공의 그 실천을 조력자·친구들이 칭찬하고 다 함께 웃으며 화합하는 장면으로 마무리. (꿈이면 깨어나 안기고, 현실이면 훈훈하게.)\n\n"

    "🚫 [유아어 및 맞춤법 금기사항]\n"
    "- 동물의 신체 부위인 '이빨' 표현은 절대 금지하며, 반드시 '이' 또는 '치아'라고 쓸 것. 치약을 삼켜도 괜찮다는 식의 오인 묘사 금지.\n"
    "- 만 0~3세 연령 특성에 맞춰 문맥에 '유치원' 단어 등장을 절대 금지하며, 반드시 '어린이집' 또는 '놀이터'로 명칭을 통일할 것.\n"
    "- 출력 직전 스스로 최종 오탈자를 검수하여 문장 부호(., ?, !)가 완벽히 끝맺어진 텍스트만 출력할 것."
)

    user_msg = (
        f"주인공 이름: {name}, 나이: {age}세, 성별: {gender}\n"
        f"성격: {child.get('personality')}\n"
        f"배경: {child.get('place')} / {child.get('time_period')}\n"
        f"분위기: {child.get('mood')}\n"
        f"문제 상황: {child.get('problem_situation')}\n"
        f"{state.get('rag_context', '')}"
    )

    if state.get("feedback") and state["feedback"] != "PASS":
        raw_feedback = state["feedback"]
        user_msg += (
            f"\n\n━━━ [수정 지시 - 아래 사항을 반드시 지켜서 처음부터 다시 써주세요] ━━━\n"
            f"{raw_feedback}\n"
            "━━━ [수정 시 절대 지켜야 할 핵심 제약] ━━━\n"
            f"- 주인공 이름은 반드시 '{name}'으로 고정하세요.\n"
            "- 동화는 반드시 [1페이지]~[4페이지] 마커로 구분된 딱 4쪽으로만 작성하세요.\n"
            "- 2쪽에서 주인공이 주어진 문제 행동(때리기, 편식, 떼쓰기 등)을 확실하게 저질러야 합니다. 착하게 참거나 이른 반성을 하면 안 됩니다.\n"
            "- 3쪽에서 조력자는 감정을 먼저 공감한 뒤 배경 소재를 활용한 대안 행동을 함께 시도해야 합니다.\n"
            "- 4쪽은 친구들과 함께 어울리는 구체적 화합 장면으로 마무리해야 합니다. 추상적 다짐 문장으로만 끝내지 마세요.\n"
            "- 이야기 텍스트 외에 해설, 팁, 등장인물 설명 등 사족을 절대 추가하지 마세요.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    response = draft_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg)
    ])

    return {"draft_ko": response.content, "revision_count": state["revision_count"] + 1}

def check_resolution_performed(draft: str, problem: str) -> tuple[bool, str]:
    """결말(4페이지)에서 주인공이 [문제 상황]의 목표 행동을 '실제로 직접 수행'하는지
    LLM 심사관으로 판정한다. 대상을 치우기/없애기/미루기/말로만 다짐하기로 끝나면 false.
    문제유형별 하드코딩 없이 편식·양치·때리기 등 전반에 일반적으로 작동한다.
    판정 실패(예외) 시엔 통과(True)로 두어 생성을 막지 않는다."""
    if not problem or not UPSTAGE_API_KEY:
        return True, ""
    system = (
        "너는 아동 행동교정 동화의 '결말 실천'을 검사하는 심사관이야. "
        "먼저 [문제 상황]에서 아이가 길러야 할 '바람직한 목표 행동'을 스스로 정하고, "
        "동화의 마지막 페이지에서 주인공이 그 목표 행동을 '직접 실제로 수행'하는지 판단해. "
        "문제의 대상을 치우기·없애기·다른 곳으로 보내기·나중으로 미루기·말로만 다짐하기로 "
        "끝나면 수행하지 않은 것(false)으로 판정해. "
        "예: 편식→채소를 실제로 먹어야 true, 양치 거부→직접 이를 닦아야 true, "
        "때리기→친구와 사이좋게 함께 놀아야 true, 정리 안 함→직접 정리해야 true.\n"
        '반드시 JSON만 출력: {"performed": true 또는 false, "target": "목표 행동", "reason": "판단 근거 한 줄"}'
    )
    try:
        resp = finalize_llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"[문제 상황]\n{problem}\n\n[동화]\n{draft}"),
        ])
        raw = resp.content.strip()
        s, e = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[s:e + 1])
        return bool(obj.get("performed", True)), str(obj.get("reason", ""))
    except Exception as ex:
        print(f"[Resolution check skipped] {ex}")
        return True, ""

def review_node(state: GraphState) -> GraphState:
    draft = state["draft_ko"]
    revision_count = state["revision_count"]
    child = state["child_info"]

    issues = []

    pages = split_story_pages(draft)
    if len(pages) != 4:
        issues.append(
            f"페이지 마커가 정확히 4개([1페이지]~[4페이지])여야 하는데 {len(pages)}개가 감지되었습니다. "
            "각 페이지 시작을 '[1페이지]' 형식으로 정확히 표기하세요."
        )

    place = (child.get("place") or "").strip()
    if place:
        place_keywords = [w for w in re.split(r"[\s,./]+", place) if len(w) > 1]
        if place_keywords and not any(kw in draft for kw in place_keywords):
            issues.append(
                f"배경 장소('{place}')가 이야기에 전혀 반영되지 않았습니다. "
                "1페이지에서 이 장소를 명확히 등장시키세요."
            )

    found_fear = [p for p in FEAR_PHRASES if p in draft]
    guilt_matches = GUILT_PATTERN_RE.findall(draft)
    if found_fear or guilt_matches:
        detail = []
        if found_fear:
            detail.append(f"공포 유발 표현: {', '.join(found_fear)}")
        if guilt_matches:
            detail.append("'~때문에 (어른이) 속상/실망/슬프다'처럼 아이 행동을 남 탓 죄책감으로 되돌리는 문장")
        issues.append(
            f"금지된 표현이 발견되었습니다 ({'; '.join(detail)}). "
            "이 표현들을 빼고, 감정을 담담하게 수용한 뒤 긍정적 대안으로 자연스럽게 이어지도록 다시 쓰세요. "
            "단, '너 오늘 속상했겠다'처럼 아이 자신의 감정을 공감해주는 문장은 괜찮으니 그대로 둬도 됩니다."
        )

    # 2, 3, 4쪽(인덱스 1~3)이 너무 길면 아이가 읽기 힘들어지므로 문장 수를 실제로 세서 검증한다.
    if len(pages) == 4:
        over_limit = []
        for page_num, page_text in zip([2, 3, 4], pages[1:4]):
            n = count_sentences(page_text)
            if n > MAX_SENTENCES_PER_PAGE:
                over_limit.append(f"{page_num}쪽({n}문장)")
        if over_limit:
            issues.append(
                f"다음 페이지가 최대 문장 수({MAX_SENTENCES_PER_PAGE}문장)를 초과했습니다: {', '.join(over_limit)}. "
                "내용을 줄이되 문장을 억지로 이어붙이지 말고, 꼭 필요한 문장만 남겨서 다시 쓰세요."
            )

    # 결말 실천 검사: 4페이지에서 주인공이 목표 행동을 실제로 수행했는지 (회피형 결말 방지)
    if len(pages) == 4:
        problem = child.get("problem_situation", "")
        performed, reason = check_resolution_performed(draft, problem)
        if not performed:
            issues.append(
                "결말(4페이지)에서 주인공이 문제 상황의 바람직한 행동을 실제로 해내지 않았습니다"
                f"{f' ({reason})' if reason else ''}. 대상을 치우거나·없애거나·미루지 말고, "
                "4페이지에서 주인공이 그 행동을 직접 수행하는 구체적 장면(예: 편식이면 채소를 진짜로 한 입 먹는)으로 다시 쓰세요."
            )

    if issues and revision_count < 3:
        feedback = "다음 문제를 모두 고쳐서 이야기를 다시 작성하세요:\n" + "\n".join(f"- {i}" for i in issues)
        print(f"[Review] Failed ({len(issues)} issue(s)): {issues}")
        return {"feedback": feedback}

    if issues:
        # 재시도 한도(3회) 초과: 무한 루프 대신 강제 통과
        print(f"[Review] Max retries reached, force-passing with residual issues: {issues}")
        return {"feedback": "PASS", "draft_ko": draft}

    print("[Review] Passed")
    return {"feedback": "PASS"}

def format_node(state: GraphState) -> GraphState:
    print("[Format] Parsing to JSON, translating, and extracting prompts...")
    child = state["child_info"]
    parser = PydanticOutputParser(pydantic_object=StoryFormat)
    
    system_prompt = (
        "You are a strict data formatter and expert children's book translator.\n"
        "Convert the provided Korean story into the exact JSON schema.\n"
        "1. Create an English `cover_image_prompt` that includes the character's age, gender, and appearance.\n"
        "2. For EACH page, provide:\n"
        "   - `text`: EXACT ORIGINAL Korean text (do not translate).\n"
        "   - `text_en`: Beautiful, rhythmic English translation of the Korean text (use single quotes only).\n"
        "   - `image_prompt`: English prompt for Stable Diffusion based on the page text. Structure: [Fixed Character Description translated to English] + [Action/Objects for the page] + [Simple background] + [, consistent character design, simple background, in watercolor children's book illustration style]\n"
        "3. Generate a short Title in Korean (max 5 words).\n"
        "4. CRITICAL RULE: The story MUST be EXACTLY 4 pages.\n\n"
        f"{parser.get_format_instructions()}"
    )
    
    user_msg = (
        f"Original Character Appearance: {child.get('appearance')}\n\n"
        f"Story Text (Korean):\n{state['draft_ko']}"
    )
    
    response = finalize_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg)
    ])
    
    original_pages = split_story_pages(state["draft_ko"])
    
    def overwrite_texts(content_list):
        if len(original_pages) == 4 and len(content_list) == 4:
            for i, page in enumerate(content_list):
                if isinstance(page, dict):
                    page["text"] = original_pages[i]
                else:
                    page.text = original_pages[i]
        return content_list

    try:
        parsed = parser.parse(response.content)
        parsed.content = overwrite_texts(parsed.content)
        return {"final_json": parsed.model_dump_json()}
    except Exception as e:
        print(f"[Format Error] {e}")
        return {"final_json": response.content}

# --- Graph Assembly 1: Draft & Revise ---
def route_draft_review(state: GraphState) -> str:
    if state["feedback"] == "PASS":
        return END
    return "draft"

draft_workflow = StateGraph(GraphState)
draft_workflow.add_node("retrieve", retrieve_node)
draft_workflow.add_node("draft", draft_node)
draft_workflow.add_node("review", review_node)

draft_workflow.add_edge(START, "retrieve")
draft_workflow.add_edge("retrieve", "draft")
draft_workflow.add_edge("draft", "review")
draft_workflow.add_conditional_edges("review", route_draft_review)

draft_app = draft_workflow.compile()

# --- Graph Assembly 2: Finalize ---
finalize_workflow = StateGraph(GraphState)
finalize_workflow.add_node("format", format_node)

finalize_workflow.add_edge(START, "format")
finalize_workflow.add_edge("format", END)

finalize_app = finalize_workflow.compile()

# =========================================================================
# 3. 메인 인터페이스 함수 (V2)
# =========================================================================

def build_initial_state(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str) -> dict:
    child_info = {
        "name": child.name,
        "age": datetime.now().year - child.birth_year,
        "gender": child.gender,
        "appearance": appearance,
        "personality": personality,
        "place": place,
        "time_period": time_period,
        "mood": mood,
        "problem_situation": problem_situation
    }
    return {
        "child_info": child_info,
        "language": language,
        "feedback": None,
        "revision_count": 0,
        "guide_text": ""
    }

# --- 문장부호 보정 -----------------------------------------------------------
# draft LLM(solar-pro3)이 "모든 문장을 문장부호로 끝맺어라" 규칙을 약 1/3 확률로
# 무시하고 마침표 없이 문장을 공백으로만 이어붙이는 경우가 있다. 이러면 가독성이
# 떨어지고 review_node의 문장 수 검사(마침표 개수 기반)도 무력화된다. 그래서 부호가
# 부족할 때만 '부호만' 채워 넣는 후처리를 둔다. (내용/띄어쓰기/페이지 마커는 보존)
_END_LIKE_RE = re.compile(r"(요|죠|다|까|래|자|줘|야|군|네)(\s|$)")

def ensure_sentence_punctuation(text: str) -> str:
    if not text or not UPSTAGE_API_KEY:
        return text
    marks = sum(text.count(c) for c in (".", "!", "?"))
    approx_sentences = len(_END_LIKE_RE.findall(text))
    # 이미 충분히 찍혀 있으면(정상 케이스) 그대로 둔다.
    if marks >= max(2, approx_sentences * 0.5):
        return text
    system = (
        "너는 한국어 문장부호 교정기야. 입력 텍스트의 내용, 단어, 띄어쓰기, 줄바꿈, "
        "'[n페이지]' 마커는 하나도 바꾸지 말고, 각 문장이 끝나는 자리에 알맞은 문장부호만 "
        "넣어라. 평서문은 마침표(.), 질문은 물음표(?), 감탄/외침은 느낌표(!)로. "
        "글자를 추가·삭제·수정하거나 문장을 다시 쓰지 마. 부호가 채워진 텍스트만 출력해."
    )
    try:
        resp = finalize_llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=text),
        ])
        fixed = resp.content.strip()
        # 안전장치: 결과가 원문 대비 크게 짧아지면(내용 손실 의심) 원문을 유지
        if len(fixed) >= len(text) * 0.8:
            return fixed
    except Exception as e:
        print(f"[Punctuation fix skipped] {e}")
    return text

def generate_draft_text(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str = "ko") -> tuple[str, str]:
    """초안 텍스트 생성"""
    if not UPSTAGE_API_KEY:
        return f"가짜 텍스트 초안입니다. (API KEY 필요)\n\n문제 상황: {problem_situation}", "가짜 지침입니다."
        
    initial_state = build_initial_state(child, appearance, personality, place, time_period, mood, problem_situation, language)
    print(f"Starting Draft Agent for {child.name}...")
    result = draft_app.invoke(initial_state)
    return ensure_sentence_punctuation(result["draft_ko"]), result.get("guide_text", "")

def revise_draft_text(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str, feedback: str) -> tuple[str, str]:
    """피드백 기반 텍스트 수정"""
    if not UPSTAGE_API_KEY:
        return f"피드백이 반영된 가짜 텍스트입니다: {feedback}", "가짜 지침입니다."
        
    initial_state = build_initial_state(child, appearance, personality, place, time_period, mood, problem_situation, language)
    initial_state["feedback"] = feedback  # 피드백 주입
    print(f"Starting Revise Agent for {child.name} with feedback: {feedback}...")
    result = draft_app.invoke(initial_state)
    return ensure_sentence_punctuation(result["draft_ko"]), result.get("guide_text", "")

def finalize_story_json(child: Any, appearance: str, language: str, final_text: str) -> dict:
    """텍스트 확정 후 영문 번역 및 이미지 프롬프트 추출 (포맷팅)"""
    if not UPSTAGE_API_KEY:
        return {
            "title": "가짜 동화 완성",
            "cover_image_prompt": "Fake cover art",
            "content_json": "[]"
        }
    
    # finalize 에서는 child_info 중 외형 정보만 주로 필요함
    child_info = {
        "name": child.name,
        "appearance": appearance
    }
    
    initial_state = {
        "child_info": child_info,
        "language": language,
        "draft_ko": final_text
    }
    
    print("Starting Finalize Agent (Translate & Format)...")
    result = finalize_app.invoke(initial_state)
    
    final_json_str = result.get("final_json", "{}")
    try:
        parsed_obj = json.loads(final_json_str)
        return {
            "title": parsed_obj.get("title", f"{child.name}의 이야기"),
            "cover_image_prompt": parsed_obj.get("cover_image_prompt", ""),
            "content_json": json.dumps(parsed_obj.get("content", []), ensure_ascii=False)
        }
    except Exception:
        return {
            "title": "Parsing Error",
            "cover_image_prompt": "",
            "content_json": "[]"
        }

# =========================================================================
# 4. 레거시 메인 인터페이스 함수 (V1 원샷 API 용도)
# =========================================================================

def route_review(state: GraphState) -> str:
    if state["feedback"] == "PASS":
        return "format"
    return "draft"

legacy_workflow = StateGraph(GraphState)
legacy_workflow.add_node("retrieve", retrieve_node)
legacy_workflow.add_node("draft", draft_node)
legacy_workflow.add_node("review", review_node)
legacy_workflow.add_node("format", format_node)

legacy_workflow.add_edge(START, "retrieve")
legacy_workflow.add_edge("retrieve", "draft")
legacy_workflow.add_edge("draft", "review")
legacy_workflow.add_conditional_edges("review", route_review, {"draft": "draft", "format": "format"})
legacy_workflow.add_edge("format", END)

fairy_tale_app_legacy = legacy_workflow.compile()

def generate_fairy_tale_with_rag(child: Any, appearance: str, personality: str, place: str, time_period: str, mood: str, problem_situation: str, language: str = "ko") -> dict:
    """기존 V1 원샷 API를 위한 레거시 호환 함수"""
    if not UPSTAGE_API_KEY:
        dummy_content = [{"page": 1, "text": f"{child.name}는 {problem_situation} 문제를 겪고 있었어요."}]
        return {
            "title": f"{child.name}의 가짜 동화 (RAG 모드)",
            "content_json": json.dumps(dummy_content, ensure_ascii=False),
            "cover_image_prompt": "A beautiful storybook cover art"
        }

    initial_state = build_initial_state(child, appearance, personality, place, time_period, mood, problem_situation, language)
    
    try:
        print(f"Starting Legacy Multi-Agent generation for {child.name} (Lang: {language})...")
        result = fairy_tale_app_legacy.invoke(initial_state)
        
        final_json_str = result.get("final_json", "{}")
        parsed_obj = json.loads(final_json_str)
        
        title = parsed_obj.get("title", f"{child.name}의 모험")
        cover_prompt = parsed_obj.get("cover_image_prompt", "A beautiful storybook cover art")
        content_array = parsed_obj.get("content", [])
        
        return {
            "title": title,
            "cover_image_prompt": cover_prompt,
            "content_json": json.dumps(content_array, ensure_ascii=False)
        }
    except Exception as e:
        print(f"Agentic Workflow Error: {e}")
        return {
            "title": f"{child.name}의 모험 (생성 실패)",
            "cover_image_prompt": "A beautiful storybook cover art",
            "content_json": json.dumps([{"page": 1, "text": "동화를 생성하는 중 오류가 발생했습니다."}], ensure_ascii=False)
        }