# RAG 검색 성능 개선 Walkthrough

SMILE 동화 생성 파이프라인의 RAG(검색 증강 생성) 검색 품질을 **측정 → 개선 → 검증**한 과정을 기록합니다.

---

## 1. 배경

SMILE은 두 종류의 지식을 RAG로 검색해 동화 생성에 활용합니다.

| 컬렉션 | 내용 | 용도 |
| --- | --- | --- |
| `childcare_guide` | 보건복지부 영유아 문제행동지도 지침서(PDF) 청크 628개 | 문제행동별 **전문가 해결 원칙** 추출 |
| `fairytale_examples` | 완성된 모범 동화 290편 | 동화 **스타일/분량 참고** (few-shot) |

검색은 [`kb_retriever.py`](kb_retriever.py)가 담당하며, 임베딩은 Upstage Solar 임베딩 모델을 사용합니다.

## 2. 문제 발견

검색 정확도를 눈으로 확인하던 중, 명백히 관련된 질의("친구를 때려요")인데도 임베딩 **거리가 0.76**로 꽤 높다는 점을 발견했습니다. 코드를 보니 색인·검색을 **단일 모델(`solar-embedding-1-large-query`)**로 처리하고 있었습니다.

> **가설:** Upstage 임베딩은 문서용(`-passage`)과 질의용(`-query`) 모델이 분리되어 있는데, 문서까지 query 모델로 임베딩하면 검색 정확도가 떨어진다.

## 3. 평가 설계 (약지도 / weak-supervision)

가이드 청크에는 주제 라벨이 없어, **문제행동 키워드 포함 여부**로 관련성을 자동 채점했습니다.

- **질의셋**: 문제행동 14종 × 2~3개 변형 = **31개** (때리기·물기·던지기·편식·떼쓰기·배변·수면·분리불안·위축·산만·거짓말·손가락 빨기·자위·욕설)
- **판정**: "정답 청크라면 포함할 키워드"가 검색 결과에 있으면 관련(relevant)
- **지표**: Hit@1 / Hit@3 / Hit@5 / MRR@5
- **A/B**: 단일 변수(문서 임베딩 모델)만 변경
  - **A (현재)**: 문서·질의 모두 `-query`
  - **B (개선)**: 문서 `-passage`, 질의 `-query`

구현: [`scripts/eval_rag.py`](scripts/eval_rag.py)

## 4. 결과

| 시스템 | 문서 임베딩 | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| A (현재) | `-query` | 0.81 | 0.94 | 1.00 | 0.882 |
| **B (개선)** | `-passage` | **0.87** | **0.97** | 1.00 | **0.927** |

**B가 top-1로 끌어올린 대표 사례 (A는 놓침):**
- "손가락을 계속 빨아요" — A 4위 → **B 1위**
- "혼자 안 자려 하고 잠투정이 심해요" — A 2위 → **B 1위**
- "떼쓰면서 나쁜 말을 해요" — A 2위 → **B 1위**

> ⚠️ B의 절대 거리(dist)가 더 높지만, 임베딩 모델이 다르면 벡터 공간 스케일이 달라 **절대 거리는 비교 불가**입니다. 판단은 순위 기반 지표(Hit@k·MRR)로 합니다.

전체 결과: [`data/rag_eval_report.md`](data/rag_eval_report.md) · [`data/rag_eval_results.csv`](data/rag_eval_results.csv)

## 5. 적용 (실제 개선)

1. **검색기 수정** — [`kb_retriever.py`](kb_retriever.py): 문서는 `-passage`로 색인, 질의는 `-query`로 임베딩해 `query_embeddings`로 검색
2. **빌드 스크립트 수정** — [`scripts/build_guide_chroma.py`](scripts/build_guide_chroma.py): 문서 색인을 `-passage`로
3. **DB 재색인** — [`scripts/reembed_passage.py`](scripts/reembed_passage.py): 기존 청크를 passage 모델로 재임베딩 (`childcare_guide` 628 + `fairytale_examples` 290)
4. **검증** — 운영 검색기 end-to-end 확인. "손가락 빨기" 질의가 이제 관련 지침을 정확히 검색

## 6. 재현 방법

```bash
# 1) A/B 평가 (재색인 前 상태에서 유효)
uv run python scripts/eval_rag.py

# 2) passage 모델로 재색인 (운영 DB 갱신)
uv run python scripts/reembed_passage.py
```

> 참고: `eval_rag.py`의 A(베이스라인)는 운영 DB를 사용합니다. 이미 passage로 재색인한 뒤에는
> A도 passage가 되어 A≈B로 나오므로, 확정 수치는 위 리포트(재색인 前 측정)를 기준으로 합니다.

## 7. 남은 과제 (Future Work)

- **우회 표현에 약함** — "손이 먼저 나가요"(때리기), "안 했다고 둘러대요"(거짓말)처럼 직접 키워드가 없는 질의는 A·B 모두 top-1을 놓침. → **쿼리 확장** 또는 **하이브리드 검색(BM25 + 벡터)** 필요.
- **거리 임계값 부재** — 검색 결과를 무조건 채택(top_k=1). 무관 질의 방어를 위한 distance 컷오프 도입 검토.

---

## 8. 동화 예시 검색 개선 (스타일 매칭으로 전환)

### 문제
`fairytale_examples`는 "문제 조건" 질의로 **완성된 이야기 JSON 전체**를 검색하는 비대칭 구조였다.
질의(문제행동+성향)와 문서(완성된 스토리, 영문 프롬프트 혼입)의 타입이 달라 매칭이 약하고,
예시의 목적(문체/분량 참고)과도 맞지 않아 **플롯 복제 위험**만 컸다.

### 접근
예시의 목적이 "스타일 참고"임을 명확히 하고, **입력자의 대상연령·분위기로 매칭**하도록 재설계.
단, 원본 데이터에는 연령·분위기 라벨이 없어(전부 '다양함/무관') **LLM으로 라벨을 1회 생성**했다.

```
[1회] LLM 라벨링   : 289편 → {대상연령대, 분위기, 문체}         (scripts/label_examples.py)
[1회] 인덱스 재구축 : '조건 요약 키'를 passage 색인, 본문은 메타데이터  (scripts/build_example_index.py)
[검색] retrieve_example : "대상 연령 N세 / 분위기 M"로 대칭 매칭, 본문(영문 제거)만 반환
[생성] retrieve_node    : 예시 질의를 나이·분위기로 변경 + "문체만 참고, 플롯 차용 금지" 강화
```

### 검증 & 발견
- 분위기별로 서로 다른 예시가 매칭됨(정상). 영문·JSON 오염 제거.
- **데이터 한계 발견**: 예시 코퍼스가 대상연령 **5~7세 288편 / 3~4세 1편**, 분량 대부분 7~8페이지.
  → **나이 매칭은 변별력 없음**, "분량 참고"도 SMILE(영유아·4페이지)과 불일치.
  → 실질 유효 신호는 **분위기(mood) 매칭**. 분량은 `review_node`의 자동 검수에 위임하는 것이 안전.
- **적용 완료**: 예시 코퍼스를 SMILE draft 파이프라인으로 생성한 **영유아 4페이지 '골든 예시' 8편**
  (분위기 4종 × 2)으로 **교체**했다. ([`scripts/build_golden_examples.py`](scripts/build_golden_examples.py),
  기록: `data/golden_examples.jsonl`) → 예시 풀이 SMILE 실제 출력(영유아·4페이지)과 정확히 일치하고,
  분위기 매칭으로 스타일 참고가 이루어진다.
