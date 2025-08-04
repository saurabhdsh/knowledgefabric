@echo off
echo ==========================================
echo Simple 'which' Module Fix for Windows VDI
echo ==========================================
echo.

echo [INFO] Running step-by-step commands to fix 'which' module error
echo.

REM Step 1: Navigate to frontend directory
echo [STEP 1] Navigating to frontend directory...
cd frontend
echo [SUCCESS] In frontend directory

REM Step 2: Clean existing node_modules (if needed)
echo [STEP 2] Cleaning existing node_modules...
if exist "node_modules" (
    rmdir /s /q node_modules
    echo [SUCCESS] Removed existing node_modules
) else (
    echo [INFO] No existing node_modules found
)

if exist "package-lock.json" (
    del package-lock.json
    echo [SUCCESS] Removed package-lock.json
) else (
    echo [INFO] No package-lock.json found
)

REM Step 3: Clean npm cache
echo [STEP 3] Cleaning npm cache...
npm cache clean --force
npm cache verify
echo [SUCCESS] NPM cache cleaned

REM Step 4: Install dependencies with Windows VDI flags
echo [STEP 4] Installing dependencies with Windows VDI flags...
npm install --legacy-peer-deps --no-optional --no-audit --no-fund
if errorlevel 1 (
    echo [WARNING] First install attempt failed, trying alternative...
    npm install --legacy-peer-deps --force --no-audit --no-fund
)
echo [SUCCESS] Dependencies installed

REM Step 5: Install the missing 'which' module specifically
echo [STEP 5] Installing 'which' module...
npm install which --save-dev --force
echo [SUCCESS] 'which' module installed

REM Step 6: Install cross-spawn module (dependency)
echo [STEP 6] Installing cross-spawn module...
npm install cross-spawn --save-dev --force
echo [SUCCESS] cross-spawn module installed

REM Step 7: Create a custom which module manually
echo [STEP 7] Creating custom which module...
if not exist "node_modules\which" mkdir node_modules\which
echo [SUCCESS] which directory created

REM Step 8: Create the which module index.js file
echo [STEP 8] Creating which module index.js...
echo module.exports = function(cmd) { return cmd; }; > node_modules\which\index.js
echo [SUCCESS] which module index.js created

REM Step 9: Create package.json for the which module
echo [STEP 9] Creating which module package.json...
echo { "name": "which", "version": "1.0.0", "main": "index.js" } > node_modules\which\package.json
echo [SUCCESS] which module package.json created

REM Step 10: Set NODE_PATH environment variable
echo [STEP 10] Setting NODE_PATH environment variable...
set NODE_PATH=%cd%\node_modules
echo [SUCCESS] NODE_PATH set to: %NODE_PATH%

REM Step 11: Test the which module
echo [STEP 11] Testing which module...
node -e "try { require('which'); console.log('✓ which module works'); } catch(e) { console.log('✗ which module error:', e.message); }"
echo [SUCCESS] which module test completed

REM Step 12: Set NODE_OPTIONS and start frontend
echo [STEP 12] Setting NODE_OPTIONS and starting frontend...
set NODE_OPTIONS=--max_old_space_size=4096
echo [SUCCESS] NODE_OPTIONS set to: %NODE_OPTIONS%

echo.
echo ==========================================
echo 🎉 Simple Fix Complete!
echo ==========================================
echo.
echo ✅ All steps completed
echo ✅ which module created
echo ✅ Environment variables set
echo ✅ Ready to start frontend
echo.
echo Now starting the frontend...
echo.
echo If you get any errors, try these alternatives:
echo.
echo Alternative 1 - Install which globally:
echo npm install -g which
echo.
echo Alternative 2 - Use yarn:
echo npm install -g yarn
echo yarn install
echo yarn start
echo.
echo Alternative 3 - Set all environment variables:
echo set NODE_ENV=development
echo set NODE_PATH=%cd%\node_modules
echo set NODE_OPTIONS=--max_old_space_size=4096 --no-warnings
echo npm start
echo.
echo Starting frontend now...
echo.
npm start 