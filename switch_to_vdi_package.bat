@echo off
echo ==========================================
echo Switch to VDI Package.json
echo ==========================================
echo.

echo [INFO] Switching to VDI-compatible package.json
echo [INFO] This will replace the current package.json with VDI version
echo.

REM Check if we're in the right directory
if not exist "frontend\package.json" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

REM Step 1: Backup current package.json
echo [STEP 1] Creating backup of current package.json...
cd frontend
copy package.json package.json.original
echo [SUCCESS] Backup created: package.json.original

REM Step 2: Replace with VDI package.json
echo [STEP 2] Switching to VDI package.json...
if exist "package_vdi.json" (
    copy package_vdi.json package.json
    echo [SUCCESS] Switched to VDI package.json
) else (
    echo [ERROR] package_vdi.json not found
    cd ..
    pause
    exit /b 1
)

REM Step 3: Clean and reinstall
echo [STEP 3] Cleaning and reinstalling dependencies...
if exist "node_modules" (
    rmdir /s /q node_modules
    echo [SUCCESS] Removed existing node_modules
)

if exist "package-lock.json" (
    del package-lock.json
    echo [SUCCESS] Removed package-lock.json
)

REM Step 4: Install with VDI compatibility
echo [STEP 4] Installing dependencies with VDI compatibility...
npm install --legacy-peer-deps --force --no-audit --no-fund
echo [SUCCESS] Dependencies installed

REM Step 5: Create VDI start script
echo [STEP 5] Creating VDI start script...
echo @echo off > start_vdi.bat
echo echo Starting Knowledge Fabric Frontend (VDI Mode)... >> start_vdi.bat
echo echo. >> start_vdi.bat
echo cd frontend >> start_vdi.bat
echo set NODE_OPTIONS=--max_old_space_size=4096 --openssl-legacy-provider >> start_vdi.bat
echo set GENERATE_SOURCEMAP=false >> start_vdi.bat
echo echo VDI compatibility mode enabled >> start_vdi.bat
echo echo NODE_OPTIONS: %%NODE_OPTIONS%% >> start_vdi.bat
echo echo GENERATE_SOURCEMAP: %%GENERATE_SOURCEMAP%% >> start_vdi.bat
echo echo. >> start_vdi.bat
echo npm run start:vdi >> start_vdi.bat

echo [SUCCESS] VDI start script created

cd ..

echo.
echo ==========================================
echo 🎉 VDI Package.json Switch Complete!
echo ==========================================
echo.
echo ✅ Switched to VDI-compatible package.json
echo ✅ Dependencies reinstalled with VDI compatibility
echo ✅ VDI start script created
echo.
echo Next steps:
echo.
echo 1. Use the VDI start script:
echo    start_vdi.bat
echo.
echo 2. Or run manually:
echo    cd frontend
echo    npm run start:vdi
echo.
echo 3. To revert to original package.json:
echo    cd frontend
echo    copy package.json.original package.json
echo    npm install
echo.
echo 4. VDI package.json includes:
echo    - Node.js v22+ compatibility
echo    - which and cross-spawn modules
echo    - Babel compatibility packages
echo    - VDI-specific environment variables
echo.
echo Happy coding! 🚀
echo.
pause 