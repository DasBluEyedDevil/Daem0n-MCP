@echo off
REM DevilMCP Setup and Run Script for Windows

echo ========================================
echo DevilMCP Setup and Run
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo Dependencies installed successfully!
echo ========================================
echo.

REM Create storage directory if it doesn't exist
if not exist "storage\" (
    echo Creating storage directory...
    mkdir storage
)

REM Copy .env.example to .env if .env doesn't exist
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
)

echo.
echo ========================================
echo Starting DevilMCP Server...
echo ========================================
echo.
echo Server will be available at: http://localhost:8080/sse
echo Press Ctrl+C to stop the server
echo.

REM Run the server
python server.py
