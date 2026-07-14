# 프로젝트 플로우 차트

FastAPI + LangGraph 멀티에이전트 RAG + MongoDB 기반의 **아동 행동교정 맞춤 동화 생성** 백엔드입니다.

---

## 1. 파일별 역할 & 의존 관계

| 파일 | 역할 |
| --- | --- |
| `main.py` | API 진입점 (FastAPI 라우터) |
| `database.py` | MongoDB(Beanie) 초기화 |
| `models.py` | DB 문서 모델 (Child / FairyTale / Feedback / ExpertGuide) |
| `schemas.py` | 요청·응답 검증 (Pydantic) |
| `llm.py` | 동화 텍스트 생성 (LangGraph 멀티에이전트) + 문장부호 보정 + 결말 검사 |
| `kb_retriever.py` | ChromaDB RAG 검색 (지침=문제행동 / 예시=분위기, passage·query 분리) |
| `image_gen.py` | 페이지별 삽화 생성 (Pollinations AI) |

### 오프라인 데이터 파이프라인 스크립트 (`scripts/`)

| 스크립트 | 역할 |
| --- | --- |
| `build_guide_chroma.py` | 전문가 PDF → passage 임베딩 → `childcare_guide` 구축 |
| `reembed_passage.py` | 기존 청크를 passage 모델로 재색인 |
| `eval_rag.py` | RAG 검색 A/B 평가 (query vs passage) |
| `label_examples.py` / `build_example_index.py` | 예시 라벨 생성 → 조건키 색인 |
| `build_golden_examples.py` | 영유아 4페이지 '골든 예시' 생성·교체 |
| `promote_rated_to_examples.py` | 평점 4점+ 실물 동화 → 예시 풀 승격 (피드백 루프) |

### 의존 방향 (호출 관계)

```mermaid
graph TD
    main[main.py<br/>FastAPI 라우터]
    llm[llm.py<br/>LangGraph + 후처리]
    kb[kb_retriever.py<br/>ChromaDB RAG]
    img[image_gen.py<br/>삽화 생성]
    models[models.py<br/>DB 문서 모델]
    schemas[schemas.py<br/>Pydantic 검증]
    db[database.py<br/>Beanie 초기화]

    solar([Upstage Solar<br/>pro3 / pro2 / embedding])
    guide[(childcare_guide<br/>전문가 지침)]
    exdb[(fairytale_examples<br/>골든+평점 예시)]
    pollin([Pollinations AI])
    mongo[(MongoDB)]
    static([static/images/*.png])

    main --> llm
    main --> img
    main --> models
    main --> schemas
    llm --> kb
    llm --> solar
    kb --> guide
    kb --> exdb
    img --> pollin
    img --> static
    models --> db
    db --> mongo
```

---

## 2. V2 메인 플로우 (Human-in-the-Loop, 실제 사용 파이프라인)

3단계로 분리되어 **사용자가 초안을 검토·수정 후 확정**하는 구조입니다.

```mermaid
flowchart TD
    A["① POST /children/{id}/fairytales/draft<br/>초안 생성"]
    A1["main.create_fairytale_draft()"]
    A2["llm.generate_draft_text()<br/>→ draft_app.invoke() (LangGraph #1)<br/>→ 문장부호 보정"]
    A3["정규식으로 [n페이지] 분할 → pages[]"]
    A4["FairyTale(status='draft') DB 저장"]
    A5(["반환: DraftRead<br/>(guide_text 육아팁, pages 초안)"])

    B["② POST /fairytales/{id}/revise<br/>피드백 수정 (반복 가능)"]
    B1["main.revise_fairytale_draft()"]
    B2["llm.revise_draft_text(feedback)<br/>→ draft_app.invoke() (feedback 주입)"]
    B3["pages 재분할 → 기존 문서 update"]

    C["③ POST /fairytales/{id}/finalize<br/>확정 → 이미지화 (SSE 스트림)"]
    C1["main.finalize_fairytale()<br/>→ StreamingResponse"]
    C2["llm.finalize_story_json()<br/>(LangGraph #2: format 노드)"]
    C3["표지+본문 루프:<br/>image_gen.generate_page_image()<br/>→ static/images/*.png"]
    C4["FairyTale(status='published') DB 저장"]
    C5(["반환: SSE data:{progress|done|error}"])

    A --> A1 --> A2 --> A3 --> A4 --> A5
    A5 -. "초안이 마음에 안 들면" .-> B
    B --> B1 --> B2 --> B3
    B3 -. "다시 수정 가능" .-> B
    B3 -. "초안 확정" .-> C
    A5 -. "바로 확정" .-> C
    C --> C1 --> C2 --> C3 --> C4 --> C5
```

> 발행(published)되고 사용자가 **별점 4점 이상**을 주면, `promote_rated_to_examples.py`가 그 동화를
> 예시 풀(`fairytale_examples`)로 승격시켜 이후 생성 품질을 높이는 **선순환 루프**를 형성합니다. (4장 참고)

---

## 3. LangGraph 내부 노드 플로우 (llm.py 핵심)

### Graph #1 — Draft & Revise (`draft_app`)

```mermaid
flowchart TD
    START([START]) --> R

    R["retrieve_node<br/>• 전문가 지침: '문제행동/성향'으로 검색<br/>• 모범 예시: '대상연령/분위기'로 검색<br/>• guide_text(육아팁) 요약 생성"]
    D["draft_node<br/>• 연령/성별/언어별 프롬프트 조립<br/>• solar-pro3로 [1~4페이지] 생성<br/>• [4페이지] 실제 교정행동 수행 강제<br/>• feedback 있으면 수정 지시 반영"]
    V["review_node (규칙 + LLM 심사)<br/>• 페이지 4개 / 배경 반영 / 금지표현 / 문장수<br/>• 결말 실천 검사(LLM): 회피형 결말 차단"]

    R -->|rag_context| D
    D -->|draft_ko| V
    V --> route{"route_draft_review()"}
    route -->|"issues & revision_count<3"| D
    route -->|"PASS"| E([END])
    E --> PUNC["generate/revise_draft_text 래퍼:<br/>ensure_sentence_punctuation()<br/>문장부호 부족 시 보정"]
```

> **결말 실천 검사**: `check_resolution_performed()`가 solar-pro2로 "주인공이 [문제 상황]의 목표 행동을
> 4페이지에서 실제로 수행했는지" 판정. 치우기·미루기·회피로 끝나면 재작성 유도. (편식→먹기, 양치거부→닦기 등 문제유형 무관)

### Graph #2 — Finalize (`finalize_app`)

```mermaid
flowchart LR
    S([START]) --> F["format_node<br/>• solar-pro2로 JSON 스키마 변환<br/>• text(한국어원문 그대로)<br/>• text_en(영역) + image_prompt<br/>• split_story_pages()로 원문 덮어쓰기"] --> E([END])
```

> **참고:** `llm.py`에는 V1 레거시 원샷 API(`fairy_tale_app_legacy` = retrieve → draft → review → format → END)도 남아있으며,
> `main.py`의 `POST /children/{id}/fairytales`가 이를 사용합니다.

---

## 4. RAG / 예시 데이터 파이프라인

전문가 지침과 모범 예시를 서로 **다른 기준**으로 검색합니다. 문서는 `passage` 모델, 질의는 `query` 모델로
임베딩하는 **비대칭 검색**으로 정확도를 높였습니다. (`eval_rag.py`: Hit@1 0.81 → 0.87)

```mermaid
flowchart TD
    subgraph BUILD["오프라인 구축"]
        PDF["보건복지부 PDF"] -->|"청크 + passage 임베딩"| GC[(childcare_guide)]
        GOLD["골든 예시 8편<br/>(draft 파이프라인 생성)"] -->|"조건키 + passage"| EC[(fairytale_examples)]
        RATED["평점 4점+ 실물 동화<br/>(피드백 루프)"] -->|"조건키 + passage"| EC
    end

    subgraph RUNTIME["생성 시 (retrieve_node)"]
        Q1["질의: 문제행동·성향"] -->|query 임베딩| GC
        Q2["질의: 대상연령·분위기"] -->|query 임베딩| EC
        GC -->|"전문가 지침 → guide_text"| OUT["rag_context"]
        EC -->|"동화 본문 → 문체/분량 참고"| OUT
    end
```

### 피드백 선순환 루프

```mermaid
flowchart LR
    FT["FairyTale<br/>(발행된 동화)"] --> RATE["사용자 별점"]
    RATE -->|"4점 이상"| FB["Feedback(rating≥4)"]
    FB --> PROMO["promote_rated_to_examples.py<br/>본문 추출 + 조건키 색인"]
    FT --> PROMO
    PROMO -->|upsert| EC[(fairytale_examples)]
    EC -->|"다음 생성 시 예시로 참고"| NEXT["더 나은 동화 생성"]
```

---

## 5. 지침 데이터 활용 상세 (원칙 이식)

전문가 지침(`childcare_guide`)은 **"검색해서 그대로 붙여넣기"가 아니라, 원칙만 뽑아 현재 이야기 배경으로 재창작**하는 방식으로 활용됩니다. 이게 단순 RAG를 넘어선 이 프로젝트의 핵심 설계입니다.

### 색인 → 검색 → 두 갈래 사용

```mermaid
flowchart TD
    PDF["보건복지부 PDF"] -->|"1000자 청크 / 200자 겹침"| CHUNK["628 청크"]
    CHUNK -->|passage 임베딩| GC[(childcare_guide)]

    Q["질의: 문제행동·성향<br/>(query 임베딩)"] -->|"top_k=1 유사도 검색"| GC
    GC --> RAW["검색된 지침 청크 (raw_guide)"]

    RAW -->|"갈래 A"| CTX["rag_context<br/>→ draft_node [3페이지] 솔루션 재료"]
    RAW -->|"갈래 B: 요약"| TIP["guide_text<br/>→ 부모용 육아팁 (로딩 화면)"]
```

### 갈래 A — 원칙 이식 (동화 생성)

지침을 그대로 옮기지 않고, **심리학적 원칙만** 추출해 **현재 이야기의 배경·소재로 재창작**합니다.

| 구분 | 예시 |
| --- | --- |
| 지침 원칙 | "신체 에너지를 발산하게 하라" |
| 지침의 구체적 소품 | 샌드백 치기 |
| 이야기 배경 | 축구장 |
| ❌ 잘못된 반영 | "샌드백을 친다" (배경과 무관한 소품 복제) |
| ✅ 올바른 반영 | **"공을 힘껏 차본다"** (원칙을 배경 소재로 재창작) |

→ 지침의 배경과 동화의 배경이 서로 달라도 **원칙만 이식**하므로 어떤 이야기 세계관에도 자연스럽게 녹아듭니다.
프롬프트가 *"지침에 나온 구체적 소품(샌드백·블록·크레파스)을 그대로 옮겨 적지 마"*를 명시적으로 강제합니다.

### 갈래 B — 부모용 육아팁 (신뢰 UX)

같은 지침을 `draft_llm`이 "부모가 바로 따라할 수 있는 4~5줄 팁"으로 요약 → 로딩 화면의 **"💡 이 동화에 쓰인 육아 지침"**.
동화가 **전문가 지침에 기반**함을 사용자에게 보여주는 신뢰 요소입니다.

### 설계 포인트 & 한계

- **청킹**: 전문가 문서라 1000자로 크게(겹침 200) 자름 → 문맥 끊김 방지
- **passage/query 분리**: 검색 정확도 향상 (Hit@1 0.81 → 0.87, `eval_rag.py`)
- **한 지침, 두 용도**: 동화 생성 재료(A) + 부모 신뢰 UX(B)
- **한계(향후 과제)**: `top_k=1`이며 거리 임계값이 없어 **무관한 질의도 무조건 1개를 반환** → distance 컷오프 도입 검토 필요

---

## 6. 데이터 모델 관계 (MongoDB)

```mermaid
erDiagram
    Child ||--o{ FairyTale : "child_id (1:N)"
    FairyTale ||--o{ Feedback : "fairy_tale_id (1:N)"

    Child {
        str name
        int birth_year
        str gender
    }
    FairyTale {
        str title
        str mood "분위기(예시 매칭 키)"
        str status "draft → published"
        str draft_text
        str guide_text
        list content "page,text,image_url,is_cover"
        ObjectId child_id
    }
    Feedback {
        int rating "1~5 (4+ → 예시 승격)"
        ObjectId fairy_tale_id
    }
    ExpertGuide {
        str chunk_id
        str content
        str source
    }
```

> `Feedback.rating`이 4 이상이면 해당 `FairyTale`이 예시 풀로 승격됩니다(4장 피드백 루프).

---

## 7. 전체 요약 시퀀스

```mermaid
sequenceDiagram
    participant U as 사용자(FE)
    participant M as main.py (FastAPI)
    participant L as llm.py (LangGraph)
    participant K as kb_retriever.py (ChromaDB)
    participant I as image_gen.py
    participant DB as MongoDB

    U->>M: POST .../draft
    M->>L: generate_draft_text()
    L->>K: retrieve_few_shot(문제행동) / retrieve_example(분위기)
    K-->>L: 전문가 지침 + 모범 예시
    Note over L: draft→review 루프<br/>(결말 실천 검사 포함)
    Note over L: 문장부호 보정
    L-->>M: draft_ko, guide_text
    M->>DB: FairyTale(status=draft) 저장
    M-->>U: DraftRead (초안 + 육아팁)

    U->>M: POST .../revise (피드백)
    M->>L: revise_draft_text(feedback)
    L-->>M: 수정된 draft
    M->>DB: 문서 update
    M-->>U: DraftRead

    U->>M: POST .../finalize
    M->>L: finalize_story_json()
    L-->>M: title, image_prompt, content_json
    loop 각 페이지
        M->>I: generate_page_image()
        I-->>M: image_url
        M-->>U: SSE progress
    end
    M->>DB: FairyTale(status=published) 저장
    M-->>U: SSE done (완성 동화)

    U->>M: POST .../feedbacks (별점)
    M->>DB: Feedback 저장
    Note over DB: 4점+ → promote_rated_to_examples.py<br/>가 예시 풀로 승격 (선순환)
```
