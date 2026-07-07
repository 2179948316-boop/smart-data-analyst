@echo off
chcp 65001 >nul
title NL2SQL Backend

:: ============================================================
::  Smart Data Analyst - Backend Startup
:: ============================================================

cd /d "%~dp0"

:: -- Check .env --
if not exist ".env" (
    echo [WARN] .env not found, copying from .env.example ...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] .env created. Please edit it and fill in DEEPSEEK_API_KEY etc.
        echo [INFO] Then re-run this script.
        pause
        exit /b 1
    ) else (
        echo [ERROR] .env.example not found either!
        pause
        exit /b 1
    )
)

:: -- Check venv --
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\
    echo [INFO]  Create one with: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r backend\requirements.txt
    pause
    exit /b 1
)

:: -- Activate venv --
call ".venv\Scripts\activate.bat"

:: -- Check backend deps --
if not exist "backend\requirements.txt" (
    echo [ERROR] backend\requirements.txt not found!
    pause
    exit /b 1
)

:: -- Start uvicorn --
echo ============================================================
echo   Smart Data Analyst - Backend
echo   http://localhost:8001
echo   API Docs: http://localhost:8001/docs
echo ============================================================
echo.

cd /d "backend"
python -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

pause
