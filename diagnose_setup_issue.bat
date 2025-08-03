@echo off
setlocal enabledelayedexpansion

REM Diagnostic script to identify why setup ends early
REM This script will help identify the exact point where setup fails

echo ==========================================
echo Setup Issue Diagnostic Tool
echo ==========================================
echo.

echo [INFO] Checking current state...

REM Check if we're in the right directory
if not exist "backend\requirements.txt" (
    echo [ERROR] Not in Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

REM Check Python virtual environment
if exist "backend\venv" (
    echo [SUCCESS] Virtual environment exists
) else (
    echo [ERROR] Virtual environment not found
    echo [INFO] Python dependencies may not be installed
)

REM Check if Python dependencies are installed
if exist "backend\venv" (
    cd backend
    call venv\Scripts\activate.bat
    python -c "import fastapi, uvicorn, pydantic" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python dependencies not properly installed
    ) else (
        echo [SUCCESS] Python dependencies installed
    )
    cd ..
)

REM Check Node.js dependencies
if exist "frontend\node_modules" (
    echo [SUCCESS] Node.js dependencies exist
) else (
    echo [ERROR] Node.js dependencies not found
)

REM Check environment file
if exist "backend\.env" (
    echo [SUCCESS] Environment file exists
) else (
    echo [ERROR] Environment file not found
)

REM Check directories
if exist "backend\uploads" (
    echo [SUCCESS] uploads directory exists
) else (
    echo [ERROR] uploads directory not found
)

if exist "backend\chroma_db" (
    echo [SUCCESS] chroma_db directory exists
) else (
    echo [ERROR] chroma_db directory not found
)

if exist "backend\models" (
    echo [SUCCESS] models directory exists
) else (
    echo [ERROR] models directory not found
)

REM Check start scripts
if exist "start_backend.bat" (
    echo [SUCCESS] start_backend.bat exists
) else (
    echo [ERROR] start_backend.bat not found
)

if exist "start_frontend.bat" (
    echo [SUCCESS] start_frontend.bat exists
) else (
    echo [ERROR] start_frontend.bat not found
)

if exist "start_all.bat" (
    echo [SUCCESS] start_all.bat exists
) else (
    echo [ERROR] start_all.bat not found
)

echo.
echo ==========================================
echo Diagnostic Complete
echo ==========================================
echo.
echo If you see many [ERROR] messages, the setup script
echo ended early after Node.js dependencies installation.
echo.
echo Try running the robust VDI setup script:
echo setup_vdi_robust.bat
echo.
pause 