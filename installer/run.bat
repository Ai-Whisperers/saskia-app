@echo off
REM ============================================================
REM Saskia RMS Fase 1 - Windows launcher
REM Per docs/operations/2026-09-tech-stack-review.md #1 (uv) + #2 (uvicorn[standard])
REM Per docs/plans/2026-08-31-rms-fase-1-dev-plan.md §9 Task 9
REM ============================================================

setlocal

REM Find the directory of this script (works whether user double-clicks or runs from cmd)
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

REM Check for uv
where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: uv is not installed.
    echo.
    echo Install it from https://astral.sh/uv or run:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)

REM Sync dependencies if needed (this is fast on uv; safe to always run)
echo Syncing dependencies...
uv sync --all-extras
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: uv sync failed. See output above.
    pause
    exit /b 1
)

REM Run the app. Bind to 127.0.0.1 only (per AGENTS.md rule + main.py assertion).
REM The browser-open happens below via a separate command that waits for the server.
echo.
echo ============================================================
echo  Saskia RMS - Sistema de gestion local
echo ============================================================
echo.
echo  Starting server at http://127.0.0.1:8765
echo  Close this window to stop the server.
echo.

REM Open browser after a 2-second delay (gives uvicorn time to start).
REM Use start /b so the browser open doesn't block the uvicorn process.
start /b "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8765"

REM Run uvicorn (foreground; this window STAYS OPEN until you close it)
uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765

REM If uvicorn exits, pause so the user sees the error
echo.
echo Server stopped.
pause
