#!/bin/bash
echo "=============================="
echo "  YM TestCase - Dev Server"
echo "=============================="
echo ""

# cleanup on exit
cleanup() {
  echo ""
  echo "Stopping servers..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "[1/2] Starting Backend (FastAPI)..."
cd backend
python3 -m uvicorn main:app --reload --port 8008 &
BACKEND_PID=$!
cd ..

sleep 2

echo "[2/2] Starting Frontend (Vite)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8008"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8008/docs"
echo ""
echo "Press Ctrl+C to stop..."

wait
