@echo off
echo ==========================================
echo Quick Fix for 'which' Module Error
echo ==========================================
echo.

echo [INFO] This script will quickly fix the 'which' module error
echo [INFO] Run this when you get the "Cannot find module 'which'" error
echo.

cd frontend

echo [STEP 1] Installing which module...
npm install which --save-dev

echo [STEP 2] Installing cross-spawn module...
npm install cross-spawn --save-dev

echo [STEP 3] Creating custom which module if needed...
if not exist "node_modules\which" (
    mkdir node_modules\which
    echo module.exports = function(cmd) { return cmd; }; > node_modules\which\index.js
    echo { "name": "which", "version": "1.0.0", "main": "index.js" } > node_modules\which\package.json
    echo [SUCCESS] Custom which module created
) else (
    echo [INFO] which module already exists
)

echo.
echo ==========================================
echo ✅ Quick Fix Applied!
echo ==========================================
echo.
echo Now try running: npm start
echo.
echo If it still doesn't work, run the full fix:
echo fix_windows_vdi_frontend.bat
echo.
pause 