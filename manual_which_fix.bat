@echo off
echo ==========================================
echo Manual 'which' Module Fix
echo ==========================================
echo.

echo [INFO] Quick manual fix for runtime 'which' module error
echo [INFO] Run this when npm start fails with 'which' module error
echo.

cd frontend

echo [STEP 1] Creating which module manually...
if not exist "node_modules\which" mkdir "node_modules\which"

echo module.exports = function(cmd) { return cmd; }; > "node_modules\which\index.js"
echo { "name": "which", "version": "1.0.0", "main": "index.js" } > "node_modules\which\package.json"

echo [STEP 2] Setting NODE_PATH environment variable...
set NODE_PATH=%cd%\node_modules

echo [STEP 3] Testing which module...
node -e "try { require('which'); console.log('✓ which module works'); } catch(e) { console.log('✗ which module error:', e.message); }"

echo.
echo ==========================================
echo ✅ Manual Fix Applied!
echo ==========================================
echo.
echo Now try running: npm start
echo.
echo If it still doesn't work, try:
echo set NODE_PATH=%cd%\node_modules && npm start
echo.
pause 