@echo off
REM ============================================================
REM Saskia RMS - Unified launcher (Path C: hosted first, local fallback)
REM Per docs/operations/2026-09-02-saskia-decision-hosted-pivot.md (Path C)
REM Per docs/operations/2026-09-02-saskia-stack-audit.md (round-2 launcher fix)
REM Per docs/operations/2026-09-02-saskia-deploy-runbook.md
REM
REM Behavior (2026-09-02):
REM   1. If hosted URL (saskia-rms.paragu-ai.com) is reachable AND returns 200
REM      → open the browser to the hosted URL. No uvicorn started. This is
REM      the "she just clicks the shortcut" experience.
REM   2. If hosted URL is unreachable (no internet, DNS failure, 5xx, etc.)
REM      → fall back to local-first: start uvicorn on 127.0.0.1:8765.
REM
REM This replaces the previous local-only launcher that had 4 bugs:
REM   - PYTHONPATH not set (uv failed to find app/)
REM   - HTTPS_ONLY=false missing (local has no TLS, cookie fails)
REM   - AIW_SASKIA_*_DIR overrides missing (used wrong path on her user profile)
REM   - Shell-launched uvicorn left orphan python.exe child when killed
REM All 4 fixed below.
REM ============================================================

setlocal

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

REM --- Path C: hosted first ---
REM The hosted URL is the source of truth for Saskia's data.
REM We probe it before falling back to local; this is the
REM "she just clicks the shortcut and logs in" UX.
set HOSTED_URL=https://saskia-rms.paragu-ai.com

REM Use PowerShell to do the reachability check (curl isn't on Windows by default).
powershell -NoProfile -ExecutionPolicy ByPass -Command ^
  "try { ^
     $r = Invoke-WebRequest -Uri '%HOSTED_URL%/healthz' -UseBasicParsing -TimeoutSec 5 -MaximumRedirection 5; ^
     if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } ^
   } catch { exit 1 }"
if %ERRORLEVEL% EQU 0 (
    REM Hosted is alive: just open the browser to it.
    echo ============================================================
    echo  Saskia RMS - Gestion Saskia
    echo ============================================================
    echo.
    echo  Conectando al servidor...
    start "" "%HOSTED_URL%"
    exit /b 0
)

REM --- Path A: local fallback ---
REM Hosted is unreachable. Start the local-first app so Saskia can
REM still work offline / when the server is down.
echo Hosted no disponible. Iniciando version local...

REM Check for uv
where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: uv no esta instalado.
    echo.
    echo Instala desde https://astral.sh/uv o corre:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)

REM Sync dependencies (idempotent; uv is fast)
uv sync --all-extras
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: uv sync fallo. Ver output arriba.
    pause
    exit /b 1
)

REM --- THE 4 FIXES FROM 2026-09-02 HANDOFF ---
REM (1) PYTHONPATH so uv can find app/ from any cwd
REM (2) HTTPS_ONLY=false because local has no TLS (cookie won't work otherwise)
REM (3) AIW_SASKIA_DATA_DIR/BACKUP_DIR/LOG_DIR so we use her user profile,
REM     not the default which would create folders under the wrong user
REM (4) Process tree: uvicorn is run via uv run, NOT via start /b. The shell
REM     stays attached; killing the .bat cleanly stops uvicorn.
set PYTHONPATH=.
set HTTPS_ONLY=false
set AIW_SASKIA_DATA_DIR=%LOCALAPPDATA%\AIW-Saskia
set AIW_SASKIA_BACKUP_DIR=%USERPROFILE%\Documents\AIW-Saskia\backups
set AIW_SASKIA_LOG_DIR=%LOCALAPPDATA%\AIW-Saskia\logs
set BIND_HOST=127.0.0.1
set PORT=8765

echo.
echo ============================================================
echo  Saskia RMS - Sistema de gestion local
echo ============================================================
echo.
echo  Iniciando servidor en http://127.0.0.1:8765
echo  Cerra esta ventana para detener el servidor.
echo.

REM Open browser after a 2-second delay (gives uvicorn time to start)
start /b "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8765"

REM Run uvicorn (foreground; this window STAYS OPEN until you close it)
uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765

REM If uvicorn exits, pause so the user sees the error
echo.
echo Servidor detenido.
pause