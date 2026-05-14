@echo off
echo ========================================================
echo          Starting CodeSense Platform...
echo ========================================================

echo.
echo [1/2] Starting FastAPI Backend (Port 8000)...
start "CodeSense Backend" cmd /c "cd backend && uvicorn main:app --reload --port 8000"

echo.
echo [2/2] Starting Next.js Frontend Dashboard (Port 3000)...
start "CodeSense Frontend" cmd /c "cd frontend && npm run dev"

echo.
echo ========================================================
echo  CodeSense is running!
echo  - Backend API: http://localhost:8000
echo  - Dashboard:   http://localhost:3000
echo ========================================================
pause
