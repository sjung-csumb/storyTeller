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
| `llm.py` | 동화 텍스트 생성 (LangGraph 멀티에이전트) |
| `kb_retriever.py` | ChromaDB RAG 검색 (전문가 지침 + 모범동화 예시) |
| `image_gen.py` | 페이지별 삽화 생성 (Pollinations AI) |

### 의존 방향 (호출 관계)

```mermaid
graph TD
    main[main.py<br/>FastAPI 라우터]
    llm[llm.py<br/>LangGraph 멀티에이전트]
    kb[kb_retriever.py<br/>ChromaDB RAG]
    img[image_gen.py<br/>삽화 생성]
    models[models.py<br/>DB 문서 모델]
    schemas[schemas.py<br/>Pydantic 검증]
    db[database.py<br/>Beanie 초기화]

    solar([Upstage Solar LLM])
    chroma[(ChromaDB<br/>guide_chroma_db)]
    pollin([Pollinations AI])
    mongo[(MongoDB)]
    static([static/images/*.png])

    main --> llm
    main --> img
    main --> models
    main --> schemas
    llm --> kb
    llm --> solar
    kb --> chroma
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
    A2["llm.generate_draft_text()<br/>→ draft_app.invoke() (LangGraph #1)"]
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

---

## 3. LangGraph 내부 노드 플로우 (llm.py 핵심)

### Graph #1 — Draft & Revise (`draft_app`)

```mermaid
flowchart TD
    START([START]) --> R

    R["retrieve_node<br/>• kb_retriever로 ChromaDB 검색<br/>• 전문가지침(few_shot)+모범동화(example)<br/>• guide_text(육아팁) 요약 생성"]
    D["draft_node<br/>• 연령/성별/언어별 프롬프트 조립<br/>• solar-pro3로 [1~4페이지] 동화 생성<br/>• feedback 있으면 수정 지시 반영"]
    V["review_node (규칙 기반 자동검수)<br/>• 페이지 4개 여부 / 배경장소 반영<br/>• 공포·죄책감 금지표현 검사<br/>• 페이지별 문장 수 초과 검사"]

    R -->|rag_context| D
    D -->|draft_ko| V
    V --> route{"route_draft_review()"}
    route -->|"PASS"| E([END])
    route -->|"issues & revision_count<3"| D

    note["※ 최대 3회 재시도, 초과 시 강제 PASS"]
```

### Graph #2 — Finalize (`finalize_app`)

```mermaid
flowchart LR
    S([START]) --> F["format_node<br/>• solar-pro2로 JSON 스키마 변환<br/>• text(한국어원문 그대로)<br/>• text_en(영역) + image_prompt<br/>• split_story_pages()로 원문 덮어쓰기"] --> E([END])
```

> **참고:** `llm.py`에는 V1 레거시 원샷 API(`fairy_tale_app_legacy` = retrieve → draft → review → format → END)도 남아있으며,
> `main.py`의 `POST /children/{id}/fairytales`가 이를 사용합니다. 이미지까지 한 번에 동기 생성하는 방식입니다.

---

## 4. 데이터 모델 관계 (MongoDB)

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
        str status "draft → published"
        str draft_text
        str guide_text
        list content "page,text,image_url,is_cover"
        ObjectId child_id
    }
    Feedback {
        int rating "1~5"
        ObjectId fairy_tale_id
    }
    ExpertGuide {
        str chunk_id
        str content
        str source
    }
```

> `ExpertGuide`는 전문가 지침 미러링용 모델이며, 현재 주 검색은 ChromaDB(`kb_retriever.py`)를 통해 이루어집니다.

---

## 5. 전체 요약 시퀀스

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
    L->>K: retrieve_few_shot / retrieve_example
    K-->>L: 전문가 지침 + 모범동화
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
```