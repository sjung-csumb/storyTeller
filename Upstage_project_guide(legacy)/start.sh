# 1. 시작 스크립트 작성 (start.sh)
# API 서버의 상태(/agent/health)와 데이터 적재 상태(/agent/seed-status)를 5초마다 체크하며,
# 시스템이 "대화 가능한 상태"가 되었을 때, 프론트엔드를 실행하도록 구성합니다.
# 1.1. 환경 설정 및 기존 프로세스 정리 (start.sh)
# 스크립트가 시작되면 가장 먼저 혹시 켜져 있을지 모르는 기존 서버들을 정리합니다. 포트 충돌을
# 방지하기 위함입니다.
#!/bin/bash
set -e # 명령어 실행 중 에러가 발생하면 즉시 스크립트 중단
export PATH="$HOME/.local/bin:$PATH"
echo "1. 기존 프로세스 종료 중..."
# 이전에 저장해둔 백엔드 PID 파일이 있다면 해당 프로세스 종료
if [ -f app.pid ]; then
    PID=$(cat app.pid)
    if ps -p $PID > /dev/null; then
        echo "- Backend(PID: $PID) 종료 중..."
        kill $PID
    fi
    rm -f app.pid
fi
# 프론트엔드도 동일하게 종료
if [ -f ui.pid ]; then
    PID=$(cat ui.pid)
    if ps -p $PID > /dev/null; then
        echo "- Frontend(PID: $PID) 종료 중..."
        kill $PID
    fi
    rm -f ui.pid
fi

# 1.2. 의존성 동기화 및 백엔드 실행 (start.sh)
# uv를 이용해 라이브러리를 최신 상태로 맞추고, FastAPI 서버를 백그라운드(&) 모드로 실행합니다.

echo "2. 의존성 설치 중..."
uv sync
echo "3. 백엔드 서버(FastAPI) 시작 중..."
# nohup: 터미널이 꺼져도 서버가 계속 돌게 함
# > app.log 2>&1: 서버 로그를 app.log 파일에 저장
# &: 백그라운드 실행
nohup uv run uvicorn main:app --host 0.0.0.0 --port 8001 > app.log 2>&1 &
# 방금 실행한 프로세스 ID($!)를 파일에 저장 (나중에 끄기 위해)
echo $! > app.pid


# 1.3. 서비스 준비 상태 대기 (Polling)
# 백엔드 서버가 켜졌다고 바로 쓸 수 있는 게 아닙니다. 데이터 시딩(Seeding)이 끝날 때까지 5초 간격으로
# 상태를 물어보며 기다립니다.
echo "4. 서비스 준비 상태 확인 중..."
while true; do
    # 1) 헬스 체크: 서버 프로세스가 떴는지 확인
    HEALTH_JSON=$(curl -s http://localhost:8001/agent/health || echo '{"status":"waiting"}')
    HEALTH_STATUS=$(echo $HEALTH_JSON | grep -o '"status":"[^"]*"' | cut -d'export PATH="\$HOME/.local/bin:\$PATH""'-f4)

    if [ "$HEALTH_STATUS" != "healthy" ]; then
        echo -ne "\r[*] 백엔드 서비스 응답 대기 중..."
        sleep 5
      continue
    fi


    # 2) 시딩 상태 체크: 데이터가 DB에 다 들어갔는지 확인
    STATUS_JSON=$(curl -s http://localhost:8001/agent/seed-status || echo '{"status":"waiting"}')
    STATUS=$(echo $STATUS_JSON | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    MESSAGE=$(echo $STATUS_JSON | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" = "completed" ]; then
        # 3) 더블 체크: 실제 DB 문서 개수 확인
        STATS_JSON=$(curl -s http://localhost:8001/agent/stats || echo '{"count":0}')
        COUNT=$(echo $STATS_JSON | grep -o '"count":[0-9]*' | cut -d':' -f2)

        if [ "$COUNT" -gt 0 ] && [ -n "$COUNT" ]; then
            echo -e "\n[✓] 서비스 및 데이터 준비 완료! (총 $COUNT 개의 문서)"
            break
        fi
    elif [ "$STATUS" = "in_progress" ]; then
        echo -ne "\r[*] 데이터 시딩 진행 중... ($MESSAGE)"
    fi

    sleep 5
done


# 1.4. 프론트엔드 실행 및 정보 출력 (start.sh)
# 모든 준비가 끝났으므로 프론트엔드를 실행합니다. 이때 BACKEND_URL 환경 변수를 주입하여
# 프론트엔드가 백엔드 위치를 알 수 있게 합니다.
echo -e "\n5. 프론트엔드 서버(Streamlit) 시작 중..."
# 프론트엔드에게 백엔드 주소 알려주기
export BACKEND_URL="http://localhost:8001"
# Streamlit 실행 (포트 8002)
nohup uv run streamlit run infra/frontend/ui.py --server.port 8002 > ui.log 2>&1 &
echo $! > ui.pid
# 접속 정보 안내
echo -e "\n-------------------------------------------------------"
echo "서비스가 성공적으로 시작되었습니다."
echo "백엔드 접속: http://localhost:8001"
echo "프론트엔드 접속: http://localhost:8002"
echo "로그 확인: tail -f app.log / tail -f ui.log"
echo "-------------------------------------------------------"

# 2. 종료 스크립트 (stop.sh)
# start.sh가 만들어둔 pid 파일을 읽어 깔끔하게 종료합니다.

set -e

echo "Stopping existing processes..."
if [ -f app.pid ]; then
    PID=$(cat app.pid)
    if ps -p $PID > /dev/null; then
        echo "Stopping Backend process $PID"
        kill $PID
    fi
    rm -f app.pid
else
    echo "No Backend PID file found"
fi
if [ -f ui.pid ]; then
    PID=$(cat ui.pid)
    if ps -p $PID > /dev/null; then
        echo "Stopping Frontend process $PID"
        kill $PID
    fi
    rm -f ui.pid
else
    echo "No Frontend PID file found"
fi

# 3. 실행 테스트
# 3.1. 로컬 터미널에서 다음의 명령어로 스크립트에 실행 권한을 줍니다.

# chmod +x start.sh stop.sh

# 3.2. 로컬 터미널에서 다음의 명령어로 스크립트를 실행합니다.
# ● “.env”아래 “CHROMA_MODE=local” 로 설정되어 있어야 합니다.

# sh start.sh
