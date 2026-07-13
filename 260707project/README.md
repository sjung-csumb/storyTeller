# 📖 SMILE: 행동 교정 동화 생성 서비스 (Backend & AI)

SMILE은 아이의 문제 상황과 성격을 바탕으로, 올바른 행동을 유도하는 맞춤형 동화를 생성해주는 AI 기반 서비스입니다. 기계적인 지시가 아닌 아이의 입장을 100% 수용하고, 놀이식 시뮬레이션을 통해 긍정적인 방향으로 행동을 교정할 수 있도록 돕습니다.

## 🛠 기술 스택

### Backend & AI
- **FastAPI / Python**
- **LLM**: 프롬프트 엔지니어링을 통한 동화 플롯 생성 규칙 최적화 (정서적 협박 금지, 놀이식 행동 시뮬레이션 적용)
- **RAG / Vector DB (ChromaDB)**

## 🚀 실행 방법

### 로컬 백엔드 실행
```bash
# Uvicorn을 이용한 서버 실행
uv run uvicorn main:app --reload

# 실행 확인
# 백엔드 API: http://localhost:8000
```
