@echo off
chcp 65001 >nul

:: ============================================================
::  Smart Data Analyst - Initialize Demo Data (first time only)
:: ============================================================

cd /d "%~dp0"

:: -- Check venv --
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo [INFO]  Create one with: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r backend\requirements.txt
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo ============================================================
echo   Initializing demo e-commerce data ...
echo   Target: MySQL localhost:3306 / ecommerce_demo
echo ============================================================
echo.

cd /d "backend"
python -X utf8 data/init_data.py

echo.
echo [OK] Data initialization complete.
echo.

pause
