"""
동화 예시 라벨 생성 (1회성, LLM 분류)
=====================================

목적:
  fairytale_examples 원본(data/formatted_human.jsonl)의 각 동화에는 대상연령/분위기
  라벨이 없다(전부 '다양함/무관'). 예시를 '입력자의 나이·분위기'로 매칭하려면 각 동화에
  라벨이 필요하므로, Solar LLM이 동화 본문을 읽고 대상연령대·분위기·문체를 분류한다.

산출물: data/example_labels.jsonl  (레코드별 1줄)
  { "id", "age_band", "mood", "style", "condition_key", "story" }
    - condition_key : 검색 색인용 '조건 요약 문장' (입력 질의와 대칭 매칭)
    - story         : few-shot 으로 넘길 한국어 본문(영문 image_prompt 제거)

실행: uv run python scripts/label_examples.py
  (이미 있으면 이어서 처리 / --force 로 전체 재생성)
"""
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SRC = "data/formatted_human.jsonl"
OUT = "data/example_labels.jsonl"
MODEL = "solar-pro2"

AGE_BANDS = ["3~4세", "5~7세"]  # 영유아 대상 2구간

SYS_PROMPT = (
    "너는 아동 그림동화를 분석하는 분류기야. 주어진 한국어 동화를 읽고, 이 동화가 "
    "'문체/분량/톤' 관점에서 어떤 독자에게 어울리는지 분류해줘. 내용(문제행동)이 아니라 "
    "표현 스타일에 집중해.\n"
    "반드시 아래 JSON 형식으로만 답하고 다른 말은 하지 마.\n"
    '{\n'
    '  "age_band": "3~4세" 또는 "5~7세",  // 문장 길이·어휘 난이도 기준 어울리는 연령대\n'
    '  "mood": "분위기를 2~4개 형용사로 (예: 따뜻하고 잔잔한, 밝고 경쾌한, 모험적이고 신나는)",\n'
    '  "style": "문체·분량 특징 한 줄 (예: 짧은 구어체 4페이지, 의성어가 풍부함)"\n'
    '}'
)


def extract_story(assistant_content: str) -> str:
    """assistant JSON에서 한국어 본문(page text)만 추출. 영문 프롬프트는 버린다."""
    try:
        obj = json.loads(assistant_content)
        pages = obj.get("content", [])
        texts = []
        for p in pages:
            t = p.get("text") if isinstance(p, dict) else None
            if t:
                texts.append(t.strip())
        if texts:
            return "\n".join(texts)
    except Exception:
        pass
    return assistant_content.strip()


def classify(client, story: str) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": f"[동화 본문]\n{story[:2500]}"},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    s, e = raw.find("{"), raw.rfind("}")
    obj = json.loads(raw[s:e + 1])
    age = obj.get("age_band", "").strip()
    if age not in AGE_BANDS:
        age = "5~7세"  # 기본값
    mood = str(obj.get("mood", "")).strip() or "따뜻한"
    style = str(obj.get("style", "")).strip()
    return {"age_band": age, "mood": mood, "style": style}


def main():
    force = "--force" in sys.argv
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("[ERROR] UPSTAGE_API_KEY 필요")
        return

    client = OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],
                    base_url="https://api.upstage.ai/v1/solar")

    recs = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
    print(f"[load] 예시 {len(recs)}편")

    done = {}
    if os.path.exists(OUT) and not force:
        for l in open(OUT, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                done[r["id"]] = r
        print(f"[resume] 기존 라벨 {len(done)}개 → 나머지만 처리")

    out_f = open(OUT, "w", encoding="utf-8")
    # 기존 것 다시 기록(순서 유지)
    for r in done.values():
        out_f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok, fail = len(done), 0
    for i, rec in enumerate(recs):
        ex_id = f"example_{i}"
        if ex_id in done:
            continue
        msgs = rec.get("messages", [])
        if len(msgs) < 2 or msgs[1].get("role") != "assistant":
            continue
        story = extract_story(msgs[1]["content"])
        try:
            label = classify(client, story)
        except Exception as e:
            fail += 1
            print(f"  [warn] {ex_id} 실패: {e}")
            continue
        condition_key = (
            f"대상 연령 {label['age_band']} / 분위기 {label['mood']} / {label['style']}"
        )
        row = {"id": ex_id, **label, "condition_key": condition_key, "story": story}
        out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        out_f.flush()
        ok += 1
        if ok % 20 == 0:
            print(f"  - labeled {ok}/{len(recs)}")

    out_f.close()
    print(f"[done] 성공 {ok}, 실패 {fail} → {OUT}")


if __name__ == "__main__":
    main()
