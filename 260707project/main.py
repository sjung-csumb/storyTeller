from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from fastapi.middleware.cors import CORSMiddleware
import json
import time

from database import init_db, get_session
from models import Child, FairyTale, Feedback
from schemas import (
    ChildCreate, ChildRead, 
    FairyTaleCreate, FairyTaleRead,
    FeedbackCreate, FeedbackRead
)
from llm import generate_fairy_tale_with_rag
from image_gen import generate_page_image

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    init_db()
    yield

app = FastAPI(
    title="FairyTale Mock API", 
    description="Solar LLM을 연동하여 동화를 생성하는 백엔드 API 서버입니다.",
    lifespan=lifespan
)

# 서빙용 정적 파일 디렉토리 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS (Allow all for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Children Endpoints ---

@app.post("/api/children", response_model=ChildRead, status_code=status.HTTP_201_CREATED)
def create_child(child: ChildCreate, session: Session = Depends(get_session)):
    db_child = Child.model_validate(child)
    session.add(db_child)
    session.commit()
    session.refresh(db_child)
    return db_child

@app.get("/api/children", response_model=List[ChildRead])
def read_children(session: Session = Depends(get_session)):
    children = session.exec(select(Child)).all()
    return children

@app.get("/api/children/{child_id}", response_model=ChildRead)
def read_child(child_id: int, session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


# --- FairyTales Endpoints ---

@app.post("/api/children/{child_id}/fairytales", response_model=FairyTaleRead, status_code=status.HTTP_201_CREATED)
def create_fairytale(child_id: int, request: FairyTaleCreate, session: Session = Depends(get_session)):
    # 1. 아동 정보 확인
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
        
    # 2. Solar LLM + RAG를 통해 맞춤형 동화 내용 생성
    generated_data = generate_fairy_tale_with_rag(
        child=child,
        appearance=request.appearance,
        personality=request.personality,
        place=request.place,
        time_period=request.time_period,
        mood=request.mood,
        problem_situation=request.problem_situation,
        language=request.language
    )
    
    # 3. DB 초기 저장 (ID를 먼저 획득하기 위함)
    db_fairytale = FairyTale(
        title=generated_data["title"],
        appearance=request.appearance,
        personality=request.personality,
        place=request.place,
        time_period=request.time_period,
        mood=request.mood,
        problem_situation=request.problem_situation,
        language=request.language,
        content_json="[]", # 임시 값
        child_id=child.id
    )
    
    session.add(db_fairytale)
    session.commit()
    session.refresh(db_fairytale)
    
    import time
    
    # 4. 커버 이미지 생성 (표지)
    cover_prompt = generated_data.get("cover_image_prompt", f"A beautiful storybook cover art for a fairy tale titled '{db_fairytale.title}'")
    cover_image_url = generate_page_image(
        image_prompt=cover_prompt,
        fairytale_id=db_fairytale.id,
        page_num=0
    )
    time.sleep(5) # 무료 API 속도 제한(Rate Limit) 방어
    
    # 5. 페이지 이미지 생성 및 JSON 배열에 커버 추가
    content_list = json.loads(generated_data["content_json"])
    
    # 0번 인덱스에 표지(Cover) 데이터를 삽입합니다.
    content_list.insert(0, {
        "page": 0,
        "is_cover": True,
        "text": db_fairytale.title,
        "image_url": cover_image_url
    })
    
    for page in content_list[1:]: # 0번 표지는 이미 처리했으므로 제외
        if "image_prompt" in page:
            image_url = generate_page_image(
                image_prompt=page.get("image_prompt", ""),
                fairytale_id=db_fairytale.id,
                page_num=page.get("page", 1)
            )
            page["image_url"] = image_url
            
            # 무료 API의 속도 제한(Rate Limit) 방어를 위해 5초 대기
            time.sleep(5)
            
    # 최종 JSON DB 저장
    db_fairytale.content_json = json.dumps(content_list, ensure_ascii=False)
    session.add(db_fairytale)
    session.commit()
    session.refresh(db_fairytale)
    
    return db_fairytale

@app.get("/api/fairytales/{fairytale_id}", response_model=FairyTaleRead)
def read_fairytale(fairytale_id: int, session: Session = Depends(get_session)):
    fairytale = session.get(FairyTale, fairytale_id)
    if not fairytale:
        raise HTTPException(status_code=404, detail="FairyTale not found")
    return fairytale

@app.get("/api/children/{child_id}/fairytales", response_model=List[FairyTaleRead])
def read_fairytales_for_child(child_id: int, session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child.fairy_tales


# --- Feedbacks Endpoints ---

@app.post("/api/fairytales/{fairytale_id}/feedbacks", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(fairytale_id: int, feedback: FeedbackCreate, session: Session = Depends(get_session)):
    fairytale = session.get(FairyTale, fairytale_id)
    if not fairytale:
        raise HTTPException(status_code=404, detail="FairyTale not found")
        
    db_feedback = Feedback.model_validate(feedback)
    db_feedback.fairy_tale_id = fairytale.id
    
    session.add(db_feedback)
    session.commit()
    session.refresh(db_feedback)
    
    return db_feedback
