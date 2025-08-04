@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo Windows VDI Frontend Fix
echo ==========================================
echo.

echo [INFO] Fixing frontend dependencies for Windows VDI environment
echo [INFO] This will resolve the 'which' module error
echo.

REM Check if we're in the right directory
if not exist "frontend\package.json" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

REM Step 1: Clean existing node_modules
echo [STEP 1] Cleaning existing node_modules...
if exist "frontend\node_modules" (
    echo [INFO] Removing existing node_modules...
    rmdir /s /q "frontend\node_modules" >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not remove node_modules completely
    ) else (
        echo [SUCCESS] Removed existing node_modules
    )
)

REM Step 2: Clean npm cache
echo [STEP 2] Cleaning npm cache...
npm cache clean --force >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Could not clean npm cache completely
) else (
    echo [SUCCESS] NPM cache cleaned
)

REM Step 3: Install dependencies with specific flags for Windows VDI
echo [STEP 3] Installing dependencies for Windows VDI...
cd frontend

REM Install with legacy peer deps and no optional dependencies
echo [INFO] Installing with legacy peer deps...
npm install --legacy-peer-deps --no-optional >nul 2>&1
if errorlevel 1 (
    echo [WARNING] First install attempt failed, trying alternative approach...
    
    REM Try with force flag
    npm install --legacy-peer-deps --force >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not install dependencies
        cd ..
        pause
        exit /b 1
    )
)

echo [SUCCESS] Dependencies installed

REM Step 4: Install missing 'which' module specifically
echo [STEP 4] Installing missing 'which' module...
npm install which --save-dev >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Could not install 'which' module specifically
) else (
    echo [SUCCESS] 'which' module installed
)

REM Step 5: Verify installation
echo [STEP 5] Verifying installation...
if exist "node_modules\which" (
    echo [SUCCESS] 'which' module found in node_modules
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

REM Step 6: Test the frontend
echo [STEP 6] Testing frontend installation...
echo [INFO] Testing npm start (this may take a moment)...
cd frontend
timeout /t 3 >nul
npm start --dry-run >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Frontend test failed, but dependencies are installed
    echo [INFO] You can try running 'npm start' manually
) else (
    echo [SUCCESS] Frontend test passed
)
cd ..

echo.
echo ==========================================
echo 🎉 Windows VDI Frontend Fix Complete!
echo ==========================================
echo.
echo Next steps:
echo.
echo 1. Try starting the frontend:
echo    cd frontend
echo    npm start
echo.
echo 2. If you still get errors, try:
echo    - Delete node_modules and package-lock.json
echo    - Run: npm install --legacy-peer-deps
echo    - Run: npm install which --save-dev
echo.
echo 3. Alternative approach if issues persist:
echo    - Use yarn instead of npm
echo    - Or use the Docker setup
echo.
echo Happy coding! 🚀
echo.
pause 