# Children's Story Generator

AI 맞춤형 행동 교정 동화 서비스의 초기 MVP입니다.

현재 버전은 API를 호출하지 않습니다. 부모가 입력한 동화 요구사항을 바탕으로 LLM에 넣을 최종 프롬프트를 미리보기로 생성합니다.

## 포함된 기능

- 아이 기본 정보 입력
- 주인공 외형 및 캐릭터 특징 입력
- 문제 상황, 교훈, 분위기, 배경 입력
- 동화 생성용 프롬프트 미리보기

## 실행 방법

streamlit_app_inline.py 사용

```bash
pip install streamlit streamlit-javascript streamlit-autorefresh
streamlit run streamlit_app_inline.py
```

브라우저에서 아래 주소를 열면 됩니다.

```text
http://localhost:8501
```

## 주의 사항

별점 평점은 위 실행 방법의 패키지(streamlit-javascript, streamlit-autorefresh)가 있어야 저장됩니다.
평점 기록은 satisfaction_ratings.json 에 저장됨
## 다음 단계

- Solar API 연결
- 생성 결과 DB 저장
- 아이 프로필 저장
- 동화 목록/상세 페이지
- 부모 피드백 기능
