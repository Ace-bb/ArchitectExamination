@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ========================================
echo System Architect Exam System - Windows Start
echo ========================================
echo.

if not exist ".env" (
    echo [WARNING] .env file not found, copying from .env.example...
    copy ".env.example" ".env" >nul
    if errorlevel 1 (
        echo [ERROR] Failed to copy .env file!
        pause
        exit /b 1
    )
    echo [INFO] .env file created. Please edit it and add your OPENAI_API_KEY
    echo.
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.7+ and add to PATH
    pause
    exit /b 1
)

if not exist "venv" (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Dependencies installed successfully
echo.
echo [STARTING] Starting System Architect Exam System...
echo [URL] Access URL: http://localhost:8000
echo [DIR] Question Bank Directory: %~dp0..\exam_questions
echo [DIR] Historical Exam Directory: %~dp0..\exam_md
echo.

python -c "import sys; print('Python Version: ' + sys.version)"
echo.

echo Starting server...
python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server failed to start! Please check the error messages above.
    echo.
    echo Possible reasons:
    echo 1. Port 8000 is already in use
    echo 2. Incorrect configuration in .env file
    echo 3. Missing dependencies
    echo 4. Question bank folder does not exist
    echo.
    pause
    exit /b 1
)

pause