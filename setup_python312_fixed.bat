@echo off
setlocal enabledelayedexpansion

REM Knowledge Fabric - Setup for Python 3.12 (Fixed Version)
REM This script is specifically optimized for Python 3.12 compatibility with better error handling

echo ==========================================
echo Knowledge Fabric - Python 3.12 Setup (Fixed)
echo ==========================================
echo.

REM Check if we're in the right directory
if not exist "backend\requirements.txt" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [INFO] Starting Python 3.12 optimized setup...

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.12 first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed. Please install Node.js 16+ first.
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)

echo [SUCCESS] Python and Node.js are installed

REM Install Python dependencies optimized for Python 3.12
echo [INFO] Installing Python dependencies (Python 3.12 optimized)...

REM Create virtual environment if it doesn't exist
if not exist "backend\venv" (
    echo [INFO] Creating Python virtual environment...
    cd backend
    python -m venv venv
    cd ..
    echo [SUCCESS] Virtual environment created
) else (
    echo [INFO] Virtual environment already exists
)

REM Activate virtual environment and install dependencies
echo [INFO] Installing Python packages (Python 3.12 optimized)...
cd backend
call venv\Scripts\activate.bat

REM Install latest build tools first
echo [INFO] Installing latest build tools for Python 3.12...
python -m pip install --upgrade pip setuptools wheel --timeout 300

REM Install packages with Python 3.12 compatibility
echo [INFO] Installing core packages (Python 3.12 compatible)...
python -m pip install fastapi uvicorn pydantic python-dotenv aiofiles --timeout 300

echo [INFO] Installing ML packages (Python 3.12 compatible)...
python -m pip install numpy --timeout 300
python -m pip install pandas --timeout 300
python -m pip install scikit-learn --timeout 300

echo [INFO] Installing PyTorch (CPU-only, Python 3.12 compatible)...
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu --timeout 600
python -m pip install transformers sentence-transformers --timeout 600

echo [INFO] Installing database packages (Python 3.12 compatible)...
python -m pip install chromadb sqlalchemy psycopg2-binary mysql-connector-python --timeout 300

echo [INFO] Installing remaining packages (Python 3.12 compatible)...
python -m pip install pypdf2 python-jose[cryptography] passlib[bcrypt] datasets accelerate pyarrow openai --timeout 300

cd ..
echo [SUCCESS] Python dependencies installed (Python 3.12 optimized)

REM Install Node.js dependencies with error handling
echo [INFO] Installing Node.js dependencies...
cd frontend
npm install --timeout=300000
if errorlevel 1 (
    echo [ERROR] Node.js dependencies installation failed
    cd ..
    pause
    exit /b 1
)
cd ..
echo [SUCCESS] Node.js dependencies installed

REM Setup environment with error handling
echo [INFO] Setting up environment configuration...

REM Copy environment file if it doesn't exist (with error handling)
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

REM Create necessary directories with error handling
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

REM Create start scripts with error handling
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
echo 🎉 Knowledge Fabric Setup Complete (Python 3.12)!
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
echo 4. For production deployment, see SETUP_WITHOUT_DOCKER.md
echo.
echo Happy coding! 🚀
echo.
pause 