@echo off
chcp 65001 >nul
title NL2SQL Frontend

:: ============================================================
::  Smart Data Analyst - Frontend Startup
:: ============================================================

cd /d "%~dp0frontend"

:: -- Check node --
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found! Please install Node.js first.
    echo [INFO]  Download: https://nodejs.org/
    pause
    exit /b 1
)

:: -- Install deps if needed --
if not exist "node_modules" (
    echo [INFO] node_modules not found, running npm install ...
    call npm install
    echo.
)

:: -- Start dev server --
echo ============================================================
echo   Smart Data Analyst - Frontend
echo   http://localhost:5173
echo ============================================================
echo.

call npm run dev

pause
