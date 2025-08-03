@echo off
setlocal enabledelayedexpansion

REM Complete Setup Script
REM This script completes the setup if the main script ends early

echo ==========================================
echo Completing Knowledge Fabric Setup
echo ==========================================
echo.

REM Check if we're in the right directory
if not exist "backend\requirements.txt" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [INFO] Completing setup process...

REM Check if dependencies are installed
echo [INFO] Checking dependencies...

REM Check Python dependencies
if exist "backend\venv" (
    cd backend
    call venv\Scripts\activate.bat
    python -c "import fastapi, uvicorn, pydantic" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python dependencies not installed. Please run setup script first.
        cd ..
        pause
        exit /b 1
    ) else (
        echo [SUCCESS] Python dependencies installed
    )
    cd ..
) else (
    echo [ERROR] Virtual environment not found. Please run setup script first.
    pause
    exit /b 1
)

REM Check Node.js dependencies
if exist "frontend\node_modules" (
    echo [SUCCESS] Node.js dependencies installed
) else (
    echo [ERROR] Node.js dependencies not found. Please run setup script first.
    pause
    exit /b 1
)

echo [SUCCESS] Dependencies verified. Continuing setup...

REM Setup environment
echo [INFO] Setting up environment configuration...

REM Copy environment file if it doesn't exist
if not exist "backend\.env" (
    if exist "env.example" (
        copy env.example backend\.env >nul 2>&1
        if errorlevel 1 (
            echo [WARNING] Could not copy env.example, creating basic .env file...
            echo # Knowledge Fabric Environment Configuration > backend\.env
            echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
            echo SECRET_KEY=your-secret-key-change-in-production >> backend\.env
            echo HOST=0.0.0.0 >> backend\.env
            echo PORT=8000 >> backend\.env
            echo CHROMA_PERSIST_DIRECTORY=./chroma_db >> backend\.env
            echo UPLOAD_DIR=./uploads >> backend\.env
        ) else (
            echo [SUCCESS] Environment file created
        )
    ) else (
        echo [WARNING] env.example not found, creating basic .env file...
        echo # Knowledge Fabric Environment Configuration > backend\.env
        echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
        echo SECRET_KEY=your-secret-key-change-in-production >> backend\.env
        echo HOST=0.0.0.0 >> backend\.env
        echo PORT=8000 >> backend\.env
        echo CHROMA_PERSIST_DIRECTORY=./chroma_db >> backend\.env
        echo UPLOAD_DIR=./uploads >> backend\.env
    )
) else (
    echo [WARNING] Environment file already exists
)

REM Create necessary directories
echo [INFO] Creating directories...
if not exist "backend\uploads" (
    mkdir backend\uploads >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not create backend\uploads directory
    ) else (
        echo [SUCCESS] Created backend\uploads directory
    )
)

if not exist "backend\chroma_db" (
    mkdir backend\chroma_db >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not create backend\chroma_db directory
    ) else (
        echo [SUCCESS] Created backend\chroma_db directory
    )
)

if not exist "backend\models" (
    mkdir backend\models >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not create backend\models directory
    ) else (
        echo [SUCCESS] Created backend\models directory
    )
)

echo [SUCCESS] Directory setup completed

REM Check ports with error handling
echo [INFO] Checking if required ports are available...

REM Check port 8000 (backend) - with error handling
netstat -an | findstr ":8000" >nul 2>&1
if errorlevel 1 (
    echo [SUCCESS] Port 8000 appears to be available
) else (
    echo [WARNING] Port 8000 may be in use. Backend may not start properly.
)

REM Check port 3000 (frontend) - with error handling
netstat -an | findstr ":3000" >nul 2>&1
if errorlevel 1 (
    echo [SUCCESS] Port 3000 appears to be available
) else (
    echo [WARNING] Port 3000 may be in use. Frontend may not start properly.
)

REM Create start scripts
echo [INFO] Creating start scripts...

REM Create backend start script
echo @echo off > start_backend.bat
echo cd backend >> start_backend.bat
echo call venv\Scripts\activate.bat >> start_backend.bat
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> start_backend.bat

REM Create frontend start script
echo @echo off > start_frontend.bat
echo cd frontend >> start_frontend.bat
echo npm start >> start_frontend.bat

REM Create combined start script
echo @echo off > start_all.bat
echo echo Starting Knowledge Fabric... >> start_all.bat
echo echo. >> start_all.bat
echo echo Starting backend... >> start_all.bat
echo cd backend >> start_all.bat
echo call venv\Scripts\activate.bat >> start_all.bat
echo start "Backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" >> start_all.bat
echo cd .. >> start_all.bat
echo echo Starting frontend... >> start_all.bat
echo cd frontend >> start_all.bat
echo start "Frontend" cmd /k "npm start" >> start_all.bat
echo cd .. >> start_all.bat
echo echo. >> start_all.bat
echo echo Knowledge Fabric is starting... >> start_all.bat
echo echo. >> start_all.bat
echo echo Access the application at: >> start_all.bat
echo echo - Frontend: http://localhost:3000 >> start_all.bat
echo echo - Backend API: http://localhost:8000 >> start_all.bat
echo echo - API Docs: http://localhost:8000/docs >> start_all.bat
echo echo. >> start_all.bat
echo pause >> start_all.bat

echo [SUCCESS] Start scripts created

REM Show final instructions
echo.
echo ==========================================
echo 🎉 Setup Completion Successful!
echo ==========================================
echo.
echo Next steps:
echo.
echo 1. Configure your environment:
echo    - Edit backend\.env file
echo    - Set your OPENAI_API_KEY
echo    - Change SECRET_KEY for production
echo.
echo 2. Start the application:
echo    - Option 1: start_all.bat (starts both servers)
echo    - Option 2: start_backend.bat (backend only)
echo    - Option 3: start_frontend.bat (frontend only)
echo.
echo 3. Access the application:
echo    - Frontend: http://localhost:3000
echo    - Backend API: http://localhost:8000
echo    - API Documentation: http://localhost:8000/docs
echo.
echo Happy coding! 🚀
echo.
pause 