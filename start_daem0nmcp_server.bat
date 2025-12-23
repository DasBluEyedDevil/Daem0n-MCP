@echo off
REM ============================================
REM Daem0nMCP HTTP Server Launcher for Windows
REM ============================================
REM This script starts the Daem0nMCP HTTP server
REM for use with Claude Code on Windows.
REM
REM Windows has known issues with stdio transport,
REM so HTTP transport is required.
REM ============================================

title Daem0nMCP Server

REM Change to the script's directory
cd /d "%~dp0"

echo.
echo         ,     ,
echo        /(     )\
echo       ^|  \   /  ^|
echo        \  \ /  /
echo         \  Y  /     Daem0nMCP Server
echo          \ ^| /      Port: 9876
echo           \^|/
echo            *
echo.

REM Start the server
python start_server.py --port 9876

REM If the server exits, pause so user can see any errors
if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with an error. Press any key to close.
    pause >nul
)
