@echo off
chcp 65001 >nul

:: ============================================================
::  Smart Data Analyst - Stop All Services
:: ============================================================

echo ============================================================
echo   Smart Data Analyst - Stopping All Services
echo ============================================================
echo.

set KILLED=0

:: -- Kill processes on port 8001 (backend) --
echo [1/2] Stopping Backend (port 8001) ...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING" 2^>nul') do (
    echo   Killing PID %%a ...
    taskkill /f /pid %%a >nul 2>&1
    set KILLED=1
)

:: -- Kill processes on port 5173 (frontend) --
echo [2/2] Stopping Frontend (port 5173) ...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING" 2^>nul') do (
    echo   Killing PID %%a ...
    taskkill /f /pid %%a >nul 2>&1
    set KILLED=1
)

if "%KILLED%"=="0" (
    echo.
    echo [INFO] No services found running on ports 8001 or 5173.
) else (
    echo.
    echo [OK] All services stopped.
)

echo.
pause
