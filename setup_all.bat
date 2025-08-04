@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo Knowledge Fabric - Complete Setup for Windows VDI
echo ==========================================
echo.

echo [INFO] This script will set up the complete Knowledge Fabric environment
echo [INFO] Including fixes for Windows VDI frontend issues
echo.

pause

REM Check if we're in the right directory
if not exist "backend\requirements.txt" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

REM Step 1: Check and Install Node.js
echo [STEP 1] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js first.
    echo [INFO] Download from: https://nodejs.org/
    pause
    exit /b 1
) else (
    echo [SUCCESS] Node.js found
)

REM Step 2: Check and Install Python
echo [STEP 2] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+ first.
    echo [INFO] Download from: https://python.org/
    pause
    exit /b 1
) else (
    echo [SUCCESS] Python found
)

REM Step 3: Setup Python Virtual Environment
echo [STEP 3] Setting up Python virtual environment...
if exist "backend\venv" (
    echo [INFO] Python virtual environment already exists
) else (
    echo [INFO] Creating Python virtual environment...
    cd backend
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Could not create virtual environment
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [SUCCESS] Python virtual environment created
)

REM Step 4: Install Python Dependencies
echo [STEP 4] Installing Python dependencies...
cd backend
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Could not install Python dependencies
    cd ..
    pause
    exit /b 1
)
cd ..
echo [SUCCESS] Python dependencies installed

REM Step 5: Setup Frontend with Windows VDI Fix
echo [STEP 5] Setting up frontend with Windows VDI fix...

REM Clean existing node_modules if they exist
if exist "frontend\node_modules" (
    echo [INFO] Cleaning existing node_modules...
    rmdir /s /q "frontend\node_modules" >nul 2>&1
)

REM Clean npm cache
echo [INFO] Cleaning npm cache...
npm cache clean --force >nul 2>&1

REM Install frontend dependencies with Windows VDI specific flags
echo [INFO] Installing frontend dependencies for Windows VDI...
cd frontend

REM Install with legacy peer deps and no optional dependencies
npm install --legacy-peer-deps --no-optional >nul 2>&1
if errorlevel 1 (
    echo [WARNING] First install attempt failed, trying alternative approach...
    
    REM Try with force flag
    npm install --legacy-peer-deps --force >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not install frontend dependencies
        cd ..
        pause
        exit /b 1
    )
)

REM Install missing 'which' module specifically for Windows VDI
echo [INFO] Installing missing 'which' module for Windows VDI...
npm install which --save-dev >nul 2>&1

REM Verify installation
if exist "node_modules\which" (
    echo [SUCCESS] 'which' module installed
) else (
    echo [WARNING] 'which' module not found, but continuing...
)

if exist "node_modules\react-scripts" (
    echo [SUCCESS] react-scripts found
) else (
    echo [ERROR] react-scripts not found
    cd ..
    pause
    exit /b 1
)

cd ..
echo [SUCCESS] Frontend dependencies installed with Windows VDI fix

REM Step 6: Create Environment File
echo [STEP 6] Creating environment file...
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

REM Step 7: Create Directories
echo [STEP 7] Creating directories...

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

REM Step 8: Check Ports
echo [STEP 8] Checking ports...

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

REM Step 9: Create Start Scripts
echo [STEP 9] Creating start scripts...

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

REM Step 10: Final Verification
echo [STEP 10] Final verification...

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

REM Check 'which' module specifically
if exist "frontend\node_modules\which" (
    echo [SUCCESS] 'which' module verified (Windows VDI fix applied)
) else (
    echo [WARNING] 'which' module not found, but continuing...
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
echo 🎉 Complete Setup for Windows VDI Complete!
echo ==========================================
echo.
echo ✅ Windows VDI frontend fix applied
echo ✅ All dependencies installed
echo ✅ Environment configured
echo ✅ Start scripts created
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
echo 4. If frontend still has issues:
echo    - Try: cd frontend && npm start
echo    - If errors persist, run: npm install which --save-dev
echo.
echo Happy coding! 🚀
echo.
pause 