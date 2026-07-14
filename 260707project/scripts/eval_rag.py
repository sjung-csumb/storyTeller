"""
RAG 검색 성능 평가 스크립트
============================

목적 (두 가지):
  1) 포트폴리오/발표 근거   : 현재 검색기(retriever)의 정확도를 정량 지표로 제시
  2) 실제 검색 품질 개선     : 임베딩 모델 구성 A/B 비교로 개선 효과 측정

비교 대상:
  A (baseline) : 현재 운영 구성. 문서·질의를 모두 `solar-embedding-1-large-query`로 임베딩
                 (data/guide_chroma_db 의 childcare_guide 컬렉션을 그대로 사용)
  B (개선안)   : 같은 청크를 `solar-embedding-1-large-passage`로 재색인하고,
                 질의는 `solar-embedding-1-large-query`로 임베딩 (Upstage 권장 방식)
                 → 바뀌는 변수는 '문서 임베딩 모델' 단 하나뿐인 공정한 A/B

평가 방식 (약지도 / weak-supervision):
  가이드 청크에는 주제 라벨이 없으므로, 각 문제행동 질의마다 '정답 청크라면 반드시 포함할
  키워드'를 정의하고, 검색된 청크가 그 키워드를 포함하면 관련(relevant)으로 판정한다.
  지표: Hit@1, Hit@3, Hit@5, MRR(@5), 평균 top-1 거리.

실행:
  uv run python scripts/eval_rag.py
결과물:
  data/rag_eval_report.md   (사람이 읽는 리포트)
  data/rag_eval_results.csv (질의별 raw 결과)
"""
import os
import csv
import sys
import shutil

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from kb_retriever import UpstageEmbeddingFunction

load_dotenv()

GUIDE_DB_PATH = "data/guide_chroma_db"
COLLECTION = "childcare_guide"
QUERY_MODEL = "solar-embedding-1-large-query"
PASSAGE_MODEL = "solar-embedding-1-large-passage"
TOP_K = 5

# B(개선안) 재색인용 임시 DB (프로젝트 오염 방지: 스크래치 경로)
TMP_DB_PATH = os.path.join(
    os.environ.get("TEMP", os.path.expanduser("~")), "rag_eval_passage_db"
)

# ---------------------------------------------------------------------------
# 평가용 라벨 질의셋 : (문제행동, 성향, [정답이면 포함할 키워드])
#   질의 문자열은 실제 retrieve_node 가 만드는 형식과 동일하게 구성한다.
#   키워드는 '하나라도' 포함되면 관련으로 판정한다.
# ---------------------------------------------------------------------------
# 문제행동별 2~3개 변형. 같은 행동은 키워드(정답 신호)를 공유한다.
QUERY_SET = [
    # 공격성(때리기)
    ("화가 나면 친구를 때려요",             "다혈질이고 활발함", ["때리", "공격", "때린"]),
    ("동생을 자꾸 때리고 밀쳐요",           "질투가 많음",      ["때리", "공격", "때린"]),
    ("마음에 안 들면 손이 먼저 나가요",      "충동적",          ["때리", "공격", "때린"]),
    # 물기
    ("친구를 자꾸 물어요",                  "말이 아직 서툼",   ["무는", "물기", "깨무", "깨물"]),
    ("화나면 엄마를 깨물어요",              "표현이 서툼",      ["무는", "물기", "깨무", "깨물"]),
    ("어린이집에서 친구를 물어 자국이 나요", "활발함",          ["무는", "물기", "깨무", "깨물"]),
    # 던지기
    ("장난감을 집어던지고 물건을 던져요",    "고집이 셈",        ["던지"]),
    ("화가 나면 블록을 마구 던져요",         "다혈질",          ["던지"]),
    # 편식
    ("밥을 안 먹고 편식이 심해요",          "예민함",          ["편식", "골고루", "먹지"]),
    ("채소는 절대 안 먹으려고 해요",        "까다로움",         ["편식", "골고루", "먹지"]),
    ("좋아하는 것만 먹고 골고루 안 먹어요",  "고집이 셈",        ["편식", "골고루", "먹지"]),
    # 떼쓰기/고집
    ("마트에서 떼를 쓰고 고집을 부려요",     "자기주장이 강함",  ["떼", "고집"]),
    ("원하는 걸 안 해주면 드러누워 떼써요",  "감정 기복이 큼",   ["떼", "고집"]),
    # 배변
    ("대소변을 잘 못 가려요",               "소극적",          ["대소변", "배변", "기저귀"]),
    ("기저귀를 떼야 하는데 자꾸 실수해요",   "예민함",          ["대소변", "배변", "기저귀"]),
    # 수면
    ("밤에 잠을 안 자고 자꾸 깨요",         "예민함",          ["수면", "잠자", "재우"]),
    ("혼자 안 자려 하고 잠투정이 심해요",    "불안이 많음",      ["수면", "잠자", "재우", "잠투정"]),
    # 분리불안
    ("엄마와 떨어지면 심하게 울어요",        "소심함",          ["분리불안", "떨어지", "격리"]),
    ("어린이집 갈 때 엄마랑 안 떨어지려 해요", "의존적",         ["분리불안", "떨어지", "격리"]),
    # 위축/소심
    ("새로운 환경에서 위축되고 소심해요",    "내성적",          ["위축", "소심", "수줍"]),
    ("낯선 사람 앞에서 말을 안 하고 숨어요",  "낯가림이 심함",   ["위축", "소심", "수줍", "낯"]),
    # 산만/과잉행동
    ("한자리에 못 앉고 산만해요",           "활동적",          ["산만", "과잉", "주의"]),
    ("잠시도 가만있지 못하고 뛰어다녀요",    "에너지가 넘침",    ["산만", "과잉", "주의"]),
    # 거짓말
    ("자꾸 거짓말을 해요",                  "상상력이 풍부함",  ["거짓말"]),
    ("안 했으면서 안 했다고 둘러대요",       "눈치가 빠름",      ["거짓말"]),
    # 손가락 빨기
    ("손가락을 계속 빨아요",                "불안이 많음",      ["손가락", "빨기", "빠는"]),
    ("잘 때 꼭 손가락을 빨아야 자요",        "예민함",          ["손가락", "빨기", "빠는"]),
    # 자위행위
    ("성기를 자꾸 만지작거려요",            "호기심이 많음",    ["자위", "성기", "만지"]),
    ("이불이나 바닥에 몸을 문질러요",        "예민함",          ["자위", "성기", "만지"]),
    # 욕설/소리지르기
    ("욕을 하고 소리를 질러요",             "충동적",          ["욕", "소리"]),
    ("떼쓰면서 나쁜 말을 해요",             "감정 표현이 서툼", ["욕", "소리", "나쁜 말"]),
]


def make_query_text(problem: str, personality: str) -> str:
    # retrieve_node 와 동일한 질의 구성
    return f"아이의 문제 행동: {problem}\n아이의 성향: {personality}\n"


def is_relevant(doc: str, keywords) -> bool:
    return any(kw in doc for kw in keywords)


def rank_metrics(docs, keywords):
    """검색된 문서 리스트(순위순)에 대해 hit@1/3/5, 첫 관련 순위 반환."""
    hits = [is_relevant(d, keywords) for d in docs]
    first_rel = next((i + 1 for i, h in enumerate(hits) if h), None)
    return {
        "hit@1": bool(hits[0]) if len(hits) >= 1 else False,
        "hit@3": any(hits[:3]),
        "hit@5": any(hits[:5]),
        "first_rel_rank": first_rel,
    }


def evaluate(name, retrieve_fn):
    """retrieve_fn(query_text) -> (docs[list[str]], distances[list[float]])"""
    rows = []
    agg = {"hit@1": 0, "hit@3": 0, "hit@5": 0, "mrr": 0.0, "dist@1": 0.0}
    for problem, personality, keywords in QUERY_SET:
        q = make_query_text(problem, personality)
        docs, dists = retrieve_fn(q)
        m = rank_metrics(docs, keywords)
        rr = (1.0 / m["first_rel_rank"]) if m["first_rel_rank"] else 0.0
        agg["hit@1"] += int(m["hit@1"])
        agg["hit@3"] += int(m["hit@3"])
        agg["hit@5"] += int(m["hit@5"])
        agg["mrr"] += rr
        agg["dist@1"] += dists[0] if dists else 0.0
        rows.append({
            "system": name,
            "problem": problem,
            "hit@1": m["hit@1"], "hit@3": m["hit@3"], "hit@5": m["hit@5"],
            "first_rel_rank": m["first_rel_rank"] or "-",
            "dist@1": round(dists[0], 4) if dists else None,
        })
    n = len(QUERY_SET)
    summary = {
        "system": name,
        "Hit@1": agg["hit@1"] / n,
        "Hit@3": agg["hit@3"] / n,
        "Hit@5": agg["hit@5"] / n,
        "MRR@5": agg["mrr"] / n,
        "mean_dist@1": agg["dist@1"] / n,
    }
    return summary, rows


def main():
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("[ERROR] UPSTAGE_API_KEY 가 필요합니다 (.env)")
        return

    client = OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],
                    base_url="https://api.upstage.ai/v1/solar")

    # --- 기존 청크/ID 로드 (A, B 공통 소스) ---
    src_client = chromadb.PersistentClient(path=GUIDE_DB_PATH)
    src_col = src_client.get_collection(COLLECTION)  # get 시엔 embedding_fn 불필요
    data = src_col.get(include=["documents"])
    docs_all = data["documents"]
    ids_all = data["ids"]
    print(f"[load] guide chunks: {len(docs_all)}")

    query_ef = UpstageEmbeddingFunction(client, model_name=QUERY_MODEL)

    # =========================================================
    # A (baseline) : 현재 운영 컬렉션. query_texts 로 검색(=query 모델)
    # =========================================================
    a_col = src_client.get_collection(COLLECTION, embedding_function=query_ef)

    def retrieve_A(q):
        r = a_col.query(query_texts=[q], n_results=TOP_K)
        return r["documents"][0], r["distances"][0]

    print("[eval] A (query-only, 현재 운영) ...")
    a_summary, a_rows = evaluate("A_query_only", retrieve_A)

    # =========================================================
    # B (개선안) : passage 모델로 재색인 → query 모델로 검색
    # =========================================================
    if os.path.exists(TMP_DB_PATH):
        shutil.rmtree(TMP_DB_PATH, ignore_errors=True)
    passage_ef = UpstageEmbeddingFunction(client, model_name=PASSAGE_MODEL)
    b_client = chromadb.PersistentClient(path=TMP_DB_PATH)
    b_col = b_client.get_or_create_collection("guide_passage",
                                              embedding_function=passage_ef)
    print(f"[build] B 재색인 (passage 모델, {len(docs_all)}개) ...")
    batch = 100
    for i in range(0, len(docs_all), batch):
        b_col.add(documents=docs_all[i:i + batch], ids=ids_all[i:i + batch])
        print(f"  - embedded {min(i + batch, len(docs_all))}/{len(docs_all)}")

    def retrieve_B(q):
        # 문서=passage 임베딩, 질의=query 임베딩 (수동 계산 후 벡터로 검색)
        qvec = query_ef([q])[0]
        r = b_col.query(query_embeddings=[qvec], n_results=TOP_K)
        return r["documents"][0], r["distances"][0]

    print("[eval] B (passage/query split, 개선안) ...")
    b_summary, b_rows = evaluate("B_passage_query", retrieve_B)

    # --- 결과 출력 (ASCII 요약: 콘솔 인코딩 안전) ---
    def line(s):
        print("{:<18} {:>7} {:>7} {:>7} {:>7} {:>12}".format(*s))
    print("\n==================== RAG A/B 결과 ====================")
    line(("system", "Hit@1", "Hit@3", "Hit@5", "MRR@5", "mean_dist@1"))
    for s in (a_summary, b_summary):
        line((s["system"], f'{s["Hit@1"]:.2f}', f'{s["Hit@3"]:.2f}',
              f'{s["Hit@5"]:.2f}', f'{s["MRR@5"]:.3f}', f'{s["mean_dist@1"]:.4f}'))

    # --- CSV 저장 ---
    csv_path = "data/rag_eval_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(a_rows[0].keys()))
        w.writeheader()
        w.writerows(a_rows + b_rows)

    # --- Markdown 리포트 저장 ---
    md_path = "data/rag_eval_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# RAG 검색 성능 평가 리포트\n\n")
        f.write(f"- 평가 질의 수: **{len(QUERY_SET)}개** (문제행동별)\n")
        f.write(f"- 가이드 청크 수: **{len(docs_all)}개**\n")
        f.write(f"- Top-K: {TOP_K} / 관련성 판정: 키워드 포함(약지도)\n\n")
        f.write("## A/B 요약\n\n")
        f.write("| 시스템 | 문서 임베딩 | Hit@1 | Hit@3 | Hit@5 | MRR@5 | 평균 top-1 거리 |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        labels = {"A_query_only": "query (현재)", "B_passage_query": "passage (개선)"}
        for s in (a_summary, b_summary):
            f.write("| {} | {} | {:.2f} | {:.2f} | {:.2f} | {:.3f} | {:.4f} |\n".format(
                s["system"], labels[s["system"]], s["Hit@1"], s["Hit@3"],
                s["Hit@5"], s["MRR@5"], s["mean_dist@1"]))
        f.write("\n## 질의별 상세\n\n")
        f.write("| 문제행동 | A hit@1 | A 첫순위 | A dist@1 | B hit@1 | B 첫순위 | B dist@1 |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        for ar, br in zip(a_rows, b_rows):
            f.write("| {} | {} | {} | {} | {} | {} | {} |\n".format(
                ar["problem"], "✅" if ar["hit@1"] else "❌", ar["first_rel_rank"],
                ar["dist@1"], "✅" if br["hit@1"] else "❌", br["first_rel_rank"],
                br["dist@1"]))
        f.write("\n> 관련성 판정은 '정답 청크라면 포함할 키워드'의 포함 여부로 자동 채점한 "
                "약지도(weak-supervision) 방식입니다. 절대 수치보다 A/B 상대 비교에 의미가 있습니다.\n")

    print(f"\n[saved] {md_path}")
    print(f"[saved] {csv_path}")


if __name__ == "__main__":
    main()
