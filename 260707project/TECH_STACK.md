# 기술 스택 플로우 차트

`pyproject.toml` · `docker-compose.yml` 기준으로 정리한 기술 스택 구조입니다.

---

## 1. 계층별 기술 스택 (Layered Architecture)

```mermaid
flowchart TB
    subgraph CLIENT["🖥️ 사용자 / 외부 노출"]
        User["사용자 브라우저"]
        Ngrok["ngrok<br/>(외부 터널링 / HTTPS 노출)"]
    end

    subgraph FRONT["🎨 Frontend Layer"]
        ST["Streamlit<br/>streamlit_app_inline.py"]
        STplus["streamlit-autorefresh<br/>streamlit-javascript"]
    end

    subgraph BACK["⚙️ Backend Layer (FastAPI)"]
        FA["FastAPI + Uvicorn<br/>main.py"]
        PY["Pydantic / pydantic-settings<br/>schemas.py (검증)"]
    end

    subgraph AI["🤖 AI / LLM Orchestration Layer"]
        LG["LangGraph<br/>멀티에이전트 워크플로우 (llm.py)"]
        LC["LangChain<br/>langchain-openai / langchain-upstage"]
        SOLAR["Upstage Solar<br/>solar-pro3 / solar-pro2 / embedding"]
    end

    subgraph RAG["📚 RAG / Vector Layer"]
        CH["ChromaDB<br/>kb_retriever.py"]
        NP["numpy / scikit-learn<br/>임베딩 처리"]
    end

    subgraph IMG["🖼️ Image Generation"]
        POL["Pollinations AI<br/>image_gen.py (requests)"]
    end

    subgraph DATA["🗄️ Data Layer"]
        BEANIE["Beanie ODM<br/>models.py"]
        MOTOR["Motor (async driver)<br/>database.py"]
        MONGO[("MongoDB")]
    end

    User --> Ngrok --> ST
    ST --> STplus
    ST -->|REST API 호출| FA
    FA --> PY
    FA --> LG
    LG --> LC --> SOLAR
    LG --> CH
    CH --> NP
    CH --> SOLAR
    FA --> POL
    FA --> BEANIE --> MOTOR --> MONGO
```

---

## 2. 카테고리별 기술 스택 요약

| 레이어 | 기술 | 용도 |
| --- | --- | --- |
| **Frontend** | Streamlit, streamlit-autorefresh, streamlit-javascript | 사용자 UI / 동화 뷰어 |
| **Backend** | FastAPI, Uvicorn | REST API 서버 / ASGI 실행 |
| **검증** | Pydantic, pydantic-settings | 요청·응답 스키마 검증 |
| **LLM 오케스트레이션** | LangGraph, LangChain | 멀티에이전트 워크플로우 (retrieve→draft→review→format) |
| **LLM 모델** | Upstage Solar (solar-pro3 / pro2 / embedding), OpenAI SDK, google-genai | 동화 텍스트 생성 / 임베딩 |
| **RAG / VectorDB** | ChromaDB, numpy, scikit-learn | 전문가 지침·모범동화 의미 검색 |
| **이미지 생성** | Pollinations AI (requests) | 페이지별 삽화 생성 |
| **Database** | MongoDB, Beanie(ODM), Motor(async), pymongo | 아동·동화·피드백 저장 |
| **Infra / 배포** | Docker, docker-compose, ngrok | 컨테이너화 / 외부 노출 |
| **Utils** | python-dotenv, json-repair, requests | 환경변수 / JSON 복구 / HTTP |

---

## 3. Docker 컨테이너 구성 (docker-compose.yml)

```mermaid
flowchart LR
    subgraph COMPOSE["docker-compose"]
        direction TB
        NG["ngrok<br/>:4040<br/>→ frontend:8501 터널"]
        FE["frontend<br/>(Streamlit)<br/>:8501<br/>Dockerfile.frontend"]
        BE["backend<br/>(FastAPI)<br/>:8000<br/>Dockerfile.backend"]
        DB[("mongodb<br/>:27018→27017<br/>mongo:latest")]
    end

    ENV1["ENV: UPSTAGE_API_KEY"]
    ENV2["ENV: NGROK_AUTHTOKEN"]
    VOL["volumes:<br/>mongodb_data / static / backup_db"]

    NG -->|depends_on| FE
    FE -->|"BACKEND_URL<br/>depends_on"| BE
    BE -->|"MONGODB_URI<br/>depends_on"| DB
    ENV1 -.-> BE
    ENV2 -.-> NG
    VOL -.-> DB
    VOL -.-> BE
```

**포트 매핑**

| 서비스 | 컨테이너 포트 | 호스트 포트 | 이미지 / 빌드 |
| --- | --- | --- | --- |
| `mongodb` | 27017 | **27018** | mongo:latest |
| `backend` | 8000 | 8000 | Dockerfile.backend |
| `frontend` | 8501 | 8501 | Dockerfile.frontend |
| `ngrok` | 4040 | 4040 | ngrok/ngrok:latest |

---

## 4. 요청 흐름으로 본 기술 스택 (End-to-End)

```mermaid
flowchart LR
    A["사용자"] --> B["ngrok<br/>(HTTPS)"]
    B --> C["Streamlit<br/>(Frontend :8501)"]
    C -->|"REST /api"| D["FastAPI<br/>(Backend :8000)"]
    D --> E["LangGraph + LangChain"]
    E --> F["Upstage Solar LLM"]
    E --> G["ChromaDB (RAG)"]
    D --> H["Pollinations AI<br/>(이미지)"]
    D --> I["Beanie / Motor"]
    I --> J[("MongoDB :27018")]
```