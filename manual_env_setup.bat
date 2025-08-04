@echo off
setlocal enabledelayedexpansion

REM Manual Environment Setup Script
REM Run this AFTER Node.js dependencies are installed

echo ==========================================
echo Manual Environment Setup
echo ==========================================
echo.

echo [INFO] This script will complete the environment setup
echo [INFO] Run this AFTER Node.js dependencies are installed
echo.

pause

REM Check if we're in the right directory
if not exist "backend\requirements.txt" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

REM Check if Node.js dependencies are installed
if exist "frontend\node_modules" (
    echo [SUCCESS] Node.js dependencies found
) else (
    echo [ERROR] Node.js dependencies not found. Please run npm install first.
    pause
    exit /b 1
)

REM Check if Python virtual environment exists
if exist "backend\venv" (
    echo [SUCCESS] Python virtual environment found
) else (
    echo [ERROR] Python virtual environment not found. Please run Python setup first.
    pause
    exit /b 1
)

echo [INFO] Starting environment setup...

REM Step 1: Create Environment File
echo [STEP 1] Creating environment file...
if not exist "backend\.env" (
    if exist "env.example" (
        echo [INFO] Copying env.example to backend\.env
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
            echo [SUCCESS] Environment file created from env.example
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

echo [SUCCESS] Environment file setup completed

REM Step 2: Create Directories
echo [STEP 2] Creating directories...

if not exist "backend\uploads" (
    echo [INFO] Creating backend\uploads directory...
    mkdir backend\uploads >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not create backend\uploads directory
    ) else (
        echo [SUCCESS] Created backend\uploads directory
    )
) else (
    echo [INFO] backend\uploads directory already exists
)

if not exist "backend\chroma_db" (
    echo [INFO] Creating backend\chroma_db directory...
    mkdir backend\chroma_db >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not create backend\chroma_db directory
    ) else (
        echo [SUCCESS] Created backend\chroma_db directory
    )
) else (
    echo [INFO] backend\chroma_db directory already exists
)

if not exist "backend\models" (
    echo [INFO] Creating backend\models directory...
    mkdir backend\models >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not create backend\models directory
    ) else (
        echo [SUCCESS] Created backend\models directory
    )
) else (
    echo [INFO] backend\models directory already exists
)

echo [SUCCESS] Directory setup completed

REM Step 3: Check Ports
echo [STEP 3] Checking ports...

echo [INFO] Checking port 8000 (backend)...
netstat -an | findstr ":8000" >nul 2>&1
if errorlevel 1 (
    echo [SUCCESS] Port 8000 appears to be available
) else (
    echo [WARNING] Port 8000 may be in use. Backend may not start properly.
)

echo [INFO] Checking port 3000 (frontend)...
netstat -an | findstr ":3000" >nul 2>&1
if errorlevel 1 (
    echo [SUCCESS] Port 3000 appears to be available
) else (
    echo [WARNING] Port 3000 may be in use. Frontend may not start properly.
)

echo [SUCCESS] Port checking completed

REM Step 4: Create Start Scripts
echo [STEP 4] Creating start scripts...

echo [INFO] Creating start_backend.bat...
echo @echo off > start_backend.bat
echo cd backend >> start_backend.bat
echo call venv\Scripts\activate.bat >> start_backend.bat
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> start_backend.bat

echo [INFO] Creating start_frontend.bat...
echo @echo off > start_frontend.bat
echo cd frontend >> start_frontend.bat
echo npm start >> start_frontend.bat

echo [INFO] Creating start_all.bat...
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

REM Step 5: Final Verification
echo [STEP 5] Final verification...

echo [INFO] Checking if all components are ready...

REM Check Python dependencies
cd backend
call venv\Scripts\activate.bat
python -c "import fastapi, uvicorn, pydantic" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python dependencies not properly installed
) else (
    echo [SUCCESS] Python dependencies verified
)
cd ..

REM Check Node.js dependencies
if exist "frontend\node_modules" (
    echo [SUCCESS] Node.js dependencies verified
) else (
    echo [ERROR] Node.js dependencies not found
)

REM Check environment file
if exist "backend\.env" (
    echo [SUCCESS] Environment file verified
) else (
    echo [ERROR] Environment file not found
)

REM Check directories
if exist "backend\uploads" (
    echo [SUCCESS] uploads directory verified
) else (
    echo [ERROR] uploads directory not found
)

if exist "backend\chroma_db" (
    echo [SUCCESS] chroma_db directory verified
) else (
    echo [ERROR] chroma_db directory not found
)

if exist "backend\models" (
    echo [SUCCESS] models directory verified
) else (
    echo [ERROR] models directory not found
)

REM Check start scripts
if exist "start_backend.bat" (
    echo [SUCCESS] start_backend.bat verified
) else (
    echo [ERROR] start_backend.bat not found
)

if exist "start_frontend.bat" (
    echo [SUCCESS] start_frontend.bat verified
) else (
    echo [ERROR] start_frontend.bat not found
)

if exist "start_all.bat" (
    echo [SUCCESS] start_all.bat verified
) else (
    echo [ERROR] start_all.bat not found
)

echo.
echo ==========================================
echo 🎉 Manual Environment Setup Complete!
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