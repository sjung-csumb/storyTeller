import json
import os
import glob

def process_label_data(target):
    # label_data 폴더 경로 지정
    data_dir = f"C:\\YHM\\{target}\\label_data" 
    
    # 결과 파일명 설정 (training -> train.jsonl / validation -> val.jsonl)
    output_filename = "train.jsonl" if target == "training" else "val.jsonl"
    output_file = f"C:\\YHM\\{output_filename}"
    
    # 폴더 내 모든 json 파일 검색
    json_files = glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True)
    
    if not json_files:
        print(f"❌ [{target}] label_data 폴더 내에 JSON 파일이 없습니다. 경로를 확인하세요.")
        return
        
    print(f"⏳ [{target}] 총 {len(json_files)}개의 라벨 데이터 변환을 시작합니다...")
    
    with open(output_file, "w", encoding="utf-8") as f_out:
        success_count = 0
        
        for file_path in json_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                
                title = data.get("title", "재미있는 동화")
                paragraphs = data.get("paragraphInfo", [])
                
                # 1. 페이지 순서대로 문단 정렬
                paragraphs_sorted = sorted(paragraphs, key=lambda x: int(x.get("srcPage", 0)))
                
                # 2. 본문 및 메타데이터 추출 통합
                full_story_list = []
                characters = set()
                settings = set()
                classifications = set()
                read_age = "유아"
                
                for p in paragraphs_sorted:
                    # 동화 본문 수집
                    text = p.get("srcText", "").strip()
                    if text:
                        full_story_list.append(text)
                    
                    # 등장인물 수집
                    char_str = p.get("character")
                    if char_str:
                        for c in char_str.split(","):
                            if c.strip(): characters.add(c.strip())
                            
                    # 배경 수집
                    set_str = p.get("setting")
                    if set_str:
                        for s in set_str.split(","):
                            if s.strip(): settings.add(s.strip())
                    
                    # 카테고리 및 연령대 수집
                    plot_info = p.get("plotSummaryInfo")
                    if plot_info and isinstance(plot_info, dict):
                        cls = plot_info.get("classification")
                        if cls: classifications.add(cls)
                        age = plot_info.get("readAge")
                        if age: read_age = age

                full_story = "\n".join(full_story_list)
                if not full_story.strip():
                    continue # 본문이 없으면 학습 제외
                
                # 수집된 정보 문자열 정돈
                classification_str = ", ".join(classifications) if classifications else "유아 발달 및 행동 교정"
                character_str = ", ".join(characters) if characters else "다양한 동물 친구들"
                setting_str = ", ".join(settings) if settings else "동화 속 마을"
                
                # 3. 맞춤형 행동교정 특화 프롬프트 설계
                prompt_text = (
                    f"카테고리: {classification_str}\n"
                    f"대상 연령: {read_age} (3~5세)\n"
                    f"동화 제목: {title}\n"
                    f"주요 등장인물: {character_str}\n"
                    f"이야기 배경: {setting_str}\n"
                    f"위 조건들을 반영하여 유아의 올바른 사회성과 긍정적인 습관 형성을 돕는 맞춤형 교육 동화를 작성해 주세요."
                )
                
                # JSONL 저장 구조 생성
                dataset_entry = {
                    "prompt": prompt_text,
                    "completion": full_story
                }
                
                f_out.write(json.dumps(dataset_entry, ensure_ascii=False) + "\n")
                success_count += 1
                
            except Exception as e:
                print(f"파일 처리 오류 ({os.path.basename(file_path)}): {e}")
                
    print(f"✅ [{target}] 변환 완료! ➡️ {output_file} (총 {success_count}개 정제됨)")

if __name__ == "__main__":
    # training 폴더와 validation 폴더를 둘 다 돌립니다.
    process_label_data("training")
    process_label_data("validation")