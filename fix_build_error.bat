@echo off
setlocal enabledelayedexpansion

REM Fix for setuptools.build_meta BackendUnavailable error
REM This script specifically addresses the build dependency issues

echo ==========================================
echo Fixing Build Dependencies Error
echo ==========================================
echo.

REM Check if we're in the right directory
if not exist "backend\venv" (
    echo [ERROR] Virtual environment not found. Please run setup script first.
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
cd backend
call venv\Scripts\activate.bat

echo [INFO] Fixing build dependencies...

REM Remove problematic packages first
echo [INFO] Removing problematic packages...
python -m pip uninstall pandas numpy scikit-learn -y

REM Install/upgrade build tools
echo [INFO] Installing build tools...
python -m pip install --upgrade pip setuptools wheel setuptools_scm --timeout 300

REM Install packages with pre-compiled wheels only
echo [INFO] Installing packages with pre-compiled wheels...

REM Core packages
python -m pip install fastapi uvicorn pydantic python-dotenv aiofiles --only-binary=all --timeout 300

REM ML packages with wheels only
python -m pip install numpy --only-binary=all --timeout 300
python -m pip install pandas --only-binary=all --timeout 300
python -m pip install scikit-learn --only-binary=all --timeout 300

REM PyTorch CPU-only
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu --only-binary=all --timeout 600
python -m pip install transformers sentence-transformers --only-binary=all --timeout 600

REM Database packages
python -m pip install chromadb sqlalchemy psycopg2-binary mysql-connector-python --only-binary=all --timeout 300

REM Remaining packages
python -m pip install pypdf2 python-jose[cryptography] passlib[bcrypt] datasets accelerate pyarrow openai --only-binary=all --timeout 300

cd ..
echo [SUCCESS] Build dependencies fixed!
echo.
echo You can now try running the application:
echo - start_backend.bat
echo - start_frontend.bat
echo.
pause 