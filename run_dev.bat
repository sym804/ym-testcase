@echo off
echo ==============================
echo   YM TestCase - Dev Server
echo ==============================
echo.

echo [1/2] Starting Backend (FastAPI)...
start "YM TestCase Backend" cmd /c "cd backend && python -m uvicorn main:app --reload --port 8008"

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
