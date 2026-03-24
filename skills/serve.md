---
name: serve
description: 백엔드(8008) + 프론트(5173) 서버 동시 시작
---

YM TestCase 백엔드와 프론트엔드 서버를 동시에 시작합니다.

1. 먼저 기존에 실행 중인 서버가 있는지 확인합니다 (localhost:8008, localhost:5173)
2. 이미 실행 중이면 "이미 실행 중" 알림
3. 꺼져있으면 백엔드(uvicorn --port 8008 --reload)와 프론트(npm run dev)를 백그라운드로 시작
4. 5초 대기 후 두 서버 모두 응답하는지 확인
5. 결과 알림

주의:
- 백엔드는 반드시 8008 포트 사용 (8000 아님 — 다른 프로젝트 전용)
- 백엔드 working directory: backend/
- 프론트 working directory: frontend/
- --reload 옵션 포함하여 코드 변경 시 자동 반영
- run_dev.sh 또는 run_dev.bat 사용 가능
