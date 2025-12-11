@echo off
echo Starting Daem0nMCP SSE Server on port 8765...
echo.
echo Leave this window open while using Claude Code.
echo Press Ctrl+C to stop the server.
echo.
cd /d "%~dp0"
python -m daem0nmcp.server --transport sse --port 8765
pause
