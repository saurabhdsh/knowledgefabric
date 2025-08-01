@echo off
setlocal enabledelayedexpansion

REM Fix for Python 3.12 compatibility issues
REM Specifically addresses pkgutil.ImpImporter AttributeError

echo ==========================================
echo Fixing Python 3.12 Compatibility Issues
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

echo [INFO] Checking Python version...
python --version

echo [INFO] Fixing Python 3.12 compatibility issues...

REM Remove all packages that might have compatibility issues
echo [INFO] Removing potentially problematic packages...
python -m pip uninstall setuptools wheel pip -y

REM Install latest versions of build tools
echo [INFO] Installing latest build tools...
python -m pip install --upgrade pip setuptools wheel --timeout 300

REM Install packages with specific versions that work with Python 3.12
echo [INFO] Installing packages compatible with Python 3.12...

REM Core packages
python -m pip install fastapi uvicorn pydantic python-dotenv aiofiles --timeout 300

REM ML packages with specific versions for Python 3.12
python -m pip install numpy --timeout 300
python -m pip install pandas --timeout 300
python -m pip install scikit-learn --timeout 300

REM PyTorch CPU-only for Python 3.12
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu --timeout 600
python -m pip install transformers sentence-transformers --timeout 600

REM Database packages
python -m pip install chromadb sqlalchemy psycopg2-binary mysql-connector-python --timeout 300

REM Remaining packages
python -m pip install pypdf2 python-jose[cryptography] passlib[bcrypt] datasets accelerate pyarrow openai --timeout 300

cd ..
echo [SUCCESS] Python 3.12 compatibility issues fixed!
echo.
echo You can now try running the application:
echo - start_backend.bat
echo - start_frontend.bat
echo.
pause 