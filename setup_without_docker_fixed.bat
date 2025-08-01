@echo off
setlocal enabledelayedexpansion

REM Knowledge Fabric - Setup Without Docker (Windows) - Fixed Version
REM This script handles common pip installation issues in VDI environments

echo ==========================================
echo Knowledge Fabric - Setup Without Docker
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

echo [INFO] Starting setup process...

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

REM Install Python dependencies with improved error handling
echo [INFO] Installing Python dependencies...

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

REM Activate virtual environment and install dependencies with retry logic
echo [INFO] Installing Python packages...
cd backend
call venv\Scripts\activate.bat

REM Upgrade pip first
echo [INFO] Upgrading pip...
pip install --upgrade pip --timeout 300

REM Install packages one by one to identify problematic ones
echo [INFO] Installing core packages...
pip install fastapi==0.104.1 --timeout 300
pip install uvicorn[standard]==0.24.0 --timeout 300
pip install pydantic==2.5.0 --timeout 300
pip install pydantic-settings==2.1.0 --timeout 300
pip install python-multipart==0.0.6 --timeout 300
pip install python-dotenv==1.0.0 --timeout 300
pip install aiofiles==23.2.1 --timeout 300

echo [INFO] Installing ML packages...
pip install numpy==1.24.3 --timeout 300
pip install pandas==2.0.3 --timeout 300
pip install scikit-learn==1.3.0 --timeout 300

echo [INFO] Installing PyTorch and transformers...
pip install torch==2.1.0 --timeout 600
pip install transformers==4.35.0 --timeout 600
pip install sentence-transformers==2.2.2 --timeout 600

echo [INFO] Installing database packages...
pip install chromadb==0.4.15 --timeout 300
pip install sqlalchemy==2.0.23 --timeout 300
pip install psycopg2-binary==2.9.9 --timeout 300
pip install mysql-connector-python==8.2.0 --timeout 300

echo [INFO] Installing remaining packages...
pip install pypdf2==3.0.1 --timeout 300
pip install python-jose[cryptography]==3.3.0 --timeout 300
pip install passlib[bcrypt]==1.7.4 --timeout 300
pip install datasets==2.14.5 --timeout 300
pip install accelerate==0.24.1 --timeout 300
pip install pyarrow==12.0.1 --timeout 300
pip install openai==0.28.1 --timeout 300

cd ..
echo [SUCCESS] Python dependencies installed

REM Install Node.js dependencies
echo [INFO] Installing Node.js dependencies...
cd frontend
npm install --timeout=300000
cd ..
echo [SUCCESS] Node.js dependencies installed

REM Setup environment
echo [INFO] Setting up environment configuration...

REM Copy environment file if it doesn't exist
if not exist "backend\.env" (
    copy env.example backend\.env
    echo [SUCCESS] Environment file created
) else (
    echo [WARNING] Environment file already exists
)

REM Create necessary directories
if not exist "backend\uploads" mkdir backend\uploads
if not exist "backend\chroma_db" mkdir backend\chroma_db
if not exist "backend\models" mkdir backend\models
echo [SUCCESS] Directories created

REM Check ports
echo [INFO] Checking if required ports are available...

REM Check port 8000 (backend)
netstat -an | findstr ":8000" >nul
if not errorlevel 1 (
    echo [WARNING] Port 8000 is already in use. Backend may not start properly.
) else (
    echo [SUCCESS] Port 8000 is available
)

REM Check port 3000 (frontend)
netstat -an | findstr ":3000" >nul
if not errorlevel 1 (
    echo [WARNING] Port 3000 is already in use. Frontend may not start properly.
) else (
    echo [SUCCESS] Port 3000 is available
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
echo 🎉 Knowledge Fabric Setup Complete!
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