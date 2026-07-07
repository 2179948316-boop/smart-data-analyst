@echo off
chcp 65001 >nul

:: ============================================================
::  Smart Data Analyst - Start All (Backend + Frontend)
:: ============================================================

cd /d "%~dp0"

echo ============================================================
echo   Smart Data Analyst - Starting All Services
echo ============================================================
echo.

:: -- Check .env --
if not exist ".env" (
    if exist ".env.example" (
        echo [WARN] .env not found, copying from .env.example ...
        copy ".env.example" ".env" >nul
        echo [INFO] .env created. Please fill in DEEPSEEK_API_KEY etc, then re-run.
        pause
        exit /b 1
    )
)

:: -- Check prerequisites --
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Python venv not found! Run: python -m venv .venv
    pause
    exit /b 1
)
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found! Install from https://nodejs.org/
    pause
    exit /b 1
)

:: -- Install frontend deps if needed --
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies ...
    cd /d "frontend"
    call npm install
    cd /d "%~dp0"
    echo.
)

:: -- Launch backend in new window --
echo [1/2] Starting Backend  (port 8001) ...
start "NL2SQL Backend" cmd /k "cd /d "%~dp0" && call start-backend.bat"

:: -- Wait a moment for backend to boot --
echo [..]  Waiting 3s for backend to initialize ...
timeout /t 3 /nobreak >nul

:: -- Launch frontend in new window --
echo [2/2] Starting Frontend (port 5173) ...
start "NL2SQL Frontend" cmd /k "cd /d "%~dp0" && call start-frontend.bat"

echo.
echo ============================================================
echo   All services launching in separate windows:
echo     Backend  : http://localhost:8001  (API Docs: /docs)
echo     Frontend : http://localhost:5173
echo ============================================================
echo.
echo Close those windows to stop services, or run stop-all.bat
echo.

pause
