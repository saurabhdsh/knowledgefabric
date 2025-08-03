@echo off
setlocal enabledelayedexpansion

REM Knowledge Fabric - Robust VDI Setup
REM This script handles common VDI environment issues and failures

echo ==========================================
echo Knowledge Fabric - Robust VDI Setup
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

echo [INFO] Starting robust VDI setup process...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.8+ first.
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

REM Install Python dependencies with VDI optimizations
echo [INFO] Installing Python dependencies (VDI optimized)...

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
echo [INFO] Installing Python packages (VDI optimized)...
cd backend
call venv\Scripts\activate.bat

REM Upgrade pip and install build tools
echo [INFO] Upgrading pip and installing build tools...
python -m pip install --upgrade pip --timeout 300
python -m pip install --upgrade setuptools wheel --timeout 300

REM Install build dependencies first
echo [INFO] Installing build dependencies...
python -m pip install setuptools wheel setuptools_scm --timeout 300

REM Install packages with pre-compiled wheels to avoid build issues
echo [INFO] Installing core packages (pre-compiled wheels)...
python -m pip install fastapi==0.104.1 --only-binary=all --timeout 300
python -m pip install uvicorn[standard]==0.24.0 --only-binary=all --timeout 300
python -m pip install pydantic==2.5.0 --only-binary=all --timeout 300
python -m pip install pydantic-settings==2.1.0 --only-binary=all --timeout 300
python -m pip install python-multipart==0.0.6 --only-binary=all --timeout 300
python -m pip install python-dotenv==1.0.0 --only-binary=all --timeout 300
python -m pip install aiofiles==23.2.1 --only-binary=all --timeout 300

echo [INFO] Installing ML packages (pre-compiled wheels)...
python -m pip install numpy==1.24.3 --only-binary=all --timeout 300
python -m pip install pandas==2.0.3 --only-binary=all --timeout 300
python -m pip install scikit-learn==1.3.0 --only-binary=all --timeout 300

echo [INFO] Installing PyTorch (CPU-only, pre-compiled)...
python -m pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu --only-binary=all --timeout 600
python -m pip install transformers==4.35.0 --only-binary=all --timeout 600
python -m pip install sentence-transformers==2.2.2 --only-binary=all --timeout 600

echo [INFO] Installing database packages (pre-compiled wheels)...
python -m pip install chromadb==0.4.15 --only-binary=all --timeout 300
python -m pip install sqlalchemy==2.0.23 --only-binary=all --timeout 300
python -m pip install psycopg2-binary==2.9.9 --only-binary=all --timeout 300
python -m pip install mysql-connector-python==8.2.0 --only-binary=all --timeout 300

echo [INFO] Installing remaining packages (pre-compiled wheels)...
python -m pip install pypdf2==3.0.1 --only-binary=all --timeout 300
python -m pip install python-jose[cryptography]==3.3.0 --only-binary=all --timeout 300
python -m pip install passlib[bcrypt]==1.7.4 --only-binary=all --timeout 300
python -m pip install datasets==2.14.5 --only-binary=all --timeout 300
python -m pip install accelerate==0.24.1 --only-binary=all --timeout 300
python -m pip install pyarrow==12.0.1 --only-binary=all --timeout 300
python -m pip install openai==0.28.1 --only-binary=all --timeout 300

cd ..
echo [SUCCESS] Python dependencies installed (VDI optimized)

REM Install Node.js dependencies
echo [INFO] Installing Node.js dependencies...
cd frontend
npm install --timeout=300000
cd ..
echo [SUCCESS] Node.js dependencies installed

REM Setup environment with error handling
echo [INFO] Setting up environment configuration...

REM Copy environment file if it doesn't exist (with error handling)
if not exist "backend\.env" (
    if exist "env.example" (
        copy env.example backend\.env >nul 2>&1
        if errorlevel 1 (
            echo [WARNING] Could not copy env.example to backend\.env
            echo [INFO] Creating empty .env file...
            echo # Knowledge Fabric Environment Configuration > backend\.env
            echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
            echo SECRET_KEY=your-secret-key-change-in-production >> backend\.env
        ) else (
            echo [SUCCESS] Environment file created
        )
    ) else (
        echo [WARNING] env.example not found, creating basic .env file...
        echo # Knowledge Fabric Environment Configuration > backend\.env
        echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
        echo SECRET_KEY=your-secret-key-change-in-production >> backend\.env
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
echo 🎉 Knowledge Fabric Setup Complete (VDI)!
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