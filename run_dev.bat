@echo off
echo ==============================
echo   YM TestCase - Dev Server
echo ==============================
echo.

REM backend\.venv 가 있으면 그것을 쓰고, 없으면 전역 python으로 폴백
set "PY=python"
if exist "backend\.venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo [1/2] Starting Backend (FastAPI)...
start "YM TestCase Backend" cmd /c "cd backend && %PY% -m uvicorn main:app --reload --port 8008"

timeout /t 2 /nobreak >nul

echo [2/2] Starting Frontend (Vite)...
start "YM TestCase Frontend" cmd /c "cd frontend && npm run dev"

echo.
echo Backend:  http://localhost:8008
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8008/docs
echo.
echo Press any key to stop...
pause >nul
