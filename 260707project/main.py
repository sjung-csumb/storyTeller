from contextlib import asynccontextmanager
from typing import List
import json
import time
import asyncio

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from beanie import PydanticObjectId

from database import init_db
from models import Child, FairyTale, Feedback
from schemas import (
    ChildCreate, ChildRead, 
    FairyTaleCreate, FairyTaleRead,
    FeedbackCreate, FeedbackRead,
    DraftRead
)
from llm import generate_fairy_tale_with_rag
from image_gen import generate_page_image

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Beanie (MongoDB)
    await init_db()
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
async def create_child(child: ChildCreate):
    db_child = Child(**child.model_dump())
    await db_child.insert()
    return db_child

@app.get("/api/children", response_model=List[ChildRead])
async def read_children():
    children = await Child.find_all().to_list()
    return children

@app.get("/api/children/{child_id}", response_model=ChildRead)
async def read_child(child_id: PydanticObjectId):
    child = await Child.get(child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


# --- FairyTales Endpoints ---

@app.post("/api/children/{child_id}/fairytales", response_model=FairyTaleRead, status_code=status.HTTP_201_CREATED)
async def create_fairytale(child_id: PydanticObjectId, request: FairyTaleCreate):
    # 1. 아동 정보 확인
    child = await Child.get(child_id)
    if not child:
        # 프론트엔드에서 Child 생성 더미 데이터를 만듭니다.
        child = Child(name="테스트용", birth_year=2021, gender="기타")
        await child.insert()
        child_id = child.id
        
    # 2. Solar LLM + RAG를 통해 맞춤형 동화 내용 생성
    # (동기 함수인 LLM은 asyncio.to_thread로 감싸거나 그냥 호출)
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
        content=[], # 임시 빈 배열
        child_id=child_id
    )
    
    await db_fairytale.insert()
    
    # 4. 커버 이미지 생성 (표지)
    cover_prompt = generated_data.get("cover_image_prompt", f"A beautiful storybook cover art for a fairy tale titled '{db_fairytale.title}'")
    cover_image_url = generate_page_image(
        image_prompt=cover_prompt,
        fairytale_id=str(db_fairytale.id),
        page_num=0
    )
    await asyncio.sleep(12) # 무료 API 속도 제한(Rate Limit) 방어를 위해 대기
    
    # 5. 페이지 이미지 생성 및 JSON 배열에 커버 추가
    content_list = json.loads(generated_data["content_json"])
    
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
                fairytale_id=str(db_fairytale.id),
                page_num=page.get("page", 1)
            )
            page["image_url"] = image_url
            
            # 무료 API의 속도 제한(Rate Limit) 방어를 위해 대기
            await asyncio.sleep(5)
            
    # 최종 Document DB 저장
    db_fairytale.content = content_list
    await db_fairytale.save()
    
    return db_fairytale

@app.get("/api/fairytales/{fairytale_id}", response_model=FairyTaleRead)
async def read_fairytale(fairytale_id: PydanticObjectId):
    fairytale = await FairyTale.get(fairytale_id)
    if not fairytale:
        raise HTTPException(status_code=404, detail="FairyTale not found")
    return fairytale

@app.get("/api/children/{child_id}/fairytales", response_model=List[FairyTaleRead])
async def read_fairytales_for_child(child_id: PydanticObjectId):
    child = await Child.get(child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    # MongoDB 쿼리 (해당 child_id를 가진 모든 동화)
    fairytales = await FairyTale.find(FairyTale.child_id == child_id).to_list()
    return fairytales


# --- Feedbacks Endpoints ---

@app.post("/api/fairytales/{fairytale_id}/feedbacks", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def create_feedback(fairytale_id: PydanticObjectId, feedback: FeedbackCreate):
    fairytale = await FairyTale.get(fairytale_id)
    if not fairytale:
        raise HTTPException(status_code=404, detail="FairyTale not found")
        
    db_feedback = Feedback(
        rating=feedback.rating,
        fairy_tale_id=fairytale_id
    )
    
    await db_feedback.insert()
    
    return db_feedback


from pydantic import BaseModel
class ReviseRequest(BaseModel):
    feedback: str

# =====================================================================
# [V2 API] 휴먼인더루프 (Human-in-the-loop) 동화 생성 파이프라인
# =====================================================================

@app.post("/api/children/{child_id}/fairytales/draft", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
async def create_fairytale_draft(child_id: PydanticObjectId, request: FairyTaleCreate):
    child = await Child.get(child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
        
    # 1. LLM 파이프라인 호출 (텍스트 초안만 생성)
    from llm import generate_draft_text
    draft_text, guide_text = generate_draft_text(
        child=child,
        appearance=request.appearance,
        personality=request.personality,
        place=request.place,
        time_period=request.time_period,
        mood=request.mood,
        problem_situation=request.problem_situation,
        language=request.language
    )
    
    import re
    # 정규식으로 '1쪽', '1페이지', '2.' 등의 페이지 헤더를 기준으로 쪼갬
    parts = re.split(r'(?:\n|^)\s*(?:[1-4]\s*쪽|[1-4]\s*페이지|page\s*[1-4]|[1-4]\s*[.:\-])\s*\n*', draft_text, flags=re.IGNORECASE)
    raw_pages = [p.strip() for p in parts if p.strip()]
    
    # 만약 헤더가 전혀 없어서 안 쪼개졌다면, 기본 \n\n 분할을 시도
    if len(raw_pages) < 2:
        raw_pages = [p.strip() for p in draft_text.split('\n\n') if p.strip()]
        
    pages = [{"text": p} for p in raw_pages]
        
    if not pages:
        pages = [{"text": draft_text}]
        
    # 2. DB에 Draft 상태로 저장
    db_fairytale = FairyTale(
        title=f"{child.name}의 이야기 초안",
        appearance=request.appearance,
        personality=request.personality,
        place=request.place,
        time_period=request.time_period,
        mood=request.mood,
        problem_situation=request.problem_situation,
        language=request.language,
        child_id=child.id,
        status="draft",
        draft_text=draft_text,
        guide_text=guide_text,
        content=pages
    )
    await db_fairytale.insert()
    
    return DraftRead(
        id=db_fairytale.id,
        title=db_fairytale.title,
        guide_text=guide_text,
        pages=pages
    )

@app.post("/api/fairytales/{fairytale_id}/revise", response_model=DraftRead)
async def revise_fairytale_draft(fairytale_id: PydanticObjectId, request: ReviseRequest):
    fairytale = await FairyTale.get(fairytale_id)
    if not fairytale:
        raise HTTPException(status_code=404, detail="FairyTale not found")
        
    child = await Child.get(fairytale.child_id)
    
    # 1. LLM 파이프라인 호출
    from llm import revise_draft_text
    revised_text, new_guide_text = revise_draft_text(
        child=child,
        appearance=fairytale.appearance,
        personality=fairytale.personality,
        place=fairytale.place,
        time_period=fairytale.time_period,
        mood=fairytale.mood,
        problem_situation=fairytale.problem_situation,
        language=fairytale.language,
        feedback=request.feedback
    )
    
    import re
    parts = re.split(r'(?:\n|^)\s*(?:[1-4]\s*쪽|[1-4]\s*페이지|page\s*[1-4]|[1-4]\s*[.:\-])\s*\n*', revised_text, flags=re.IGNORECASE)
    raw_pages = [p.strip() for p in parts if p.strip()]
    
    if len(raw_pages) < 2:
        raw_pages = [p.strip() for p in revised_text.split('\n\n') if p.strip()]
        
    pages = [{"text": p} for p in raw_pages]
        
    if not pages:
        pages = [{"text": revised_text}]
        
    # 2. DB 업데이트
    fairytale.draft_text = revised_text
    fairytale.content = pages
    if new_guide_text:
        fairytale.guide_text = new_guide_text
    await fairytale.save()
    
    return DraftRead(
        id=fairytale.id,
        title=fairytale.title,
        guide_text=fairytale.guide_text,
        pages=pages
    )

@app.post("/api/fairytales/{fairytale_id}/finalize")
async def finalize_fairytale(fairytale_id: PydanticObjectId):
    fairytale = await FairyTale.get(fairytale_id)
    if not fairytale:
        raise HTTPException(status_code=404, detail="FairyTale not found")
        
    child = await Child.get(fairytale.child_id)
    
    async def event_generator():
        try:
            yield f'data: {{"status": "progress", "message": "그림 프롬프트를 준비하고 있어요..."}}\n\n'
            
            # 1. LLM 파이프라인 호출
            from llm import finalize_story_json
            import asyncio
            final_result = await asyncio.to_thread(
                finalize_story_json,
                child, fairytale.appearance, fairytale.language, fairytale.draft_text or "내용 없음"
            )
            
            title = final_result.get("title", fairytale.title)
            cover_prompt = final_result.get("cover_image_prompt", "")
            content_json_str = final_result.get("content_json", "[]")
            
            import json
            content_array = json.loads(content_json_str)
            
            from image_gen import generate_page_image
            
            final_content = []
            
            # 표지 (page 0)
            yield f'data: {{"status": "progress", "message": "동화책 표지를 그리고 있어요..."}}\n\n'
            cover_url = await asyncio.to_thread(generate_page_image, cover_prompt, str(fairytale.id), 0)
            await asyncio.sleep(2)
            
            final_content.append({
                "page": 0,
                "is_cover": True,
                "image_url": cover_url,
                "text": title
            })
            
            # 본문 (page 1 ~ N)
            total_pages = len(content_array)
            for i, page_obj in enumerate(content_array):
                yield f'data: {{"status": "progress", "message": "{i+1}/{total_pages} 페이지 그림을 그리고 있어요..."}}\n\n'
                img_prompt = page_obj.get("image_prompt", "")
                img_url = await asyncio.to_thread(generate_page_image, img_prompt, str(fairytale.id), i + 1)
                
                final_content.append({
                    "page": i + 1,
                    "text": page_obj.get("text", ""),
                    "image_url": img_url
                })
                
                await asyncio.sleep(2)
            
            # 3. DB 최종 업데이트
            fairytale.title = title
            fairytale.content = final_content
            fairytale.status = "published"
            await fairytale.save()
            
            # 완료 전송
            result_json = json.dumps({
                "id": str(fairytale.id),
                "title": fairytale.title,
                "content": final_content
            }, ensure_ascii=False)
            yield f'data: {{"status": "done", "result": {result_json}}}\n\n'
            
        except Exception as e:
            err_msg = json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)
            yield f'data: {err_msg}\n\n'
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
