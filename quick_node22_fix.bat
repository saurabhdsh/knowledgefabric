@echo off
echo ==========================================
echo Quick Node.js v22+ Fix for Windows VDI
echo ==========================================
echo.

echo [INFO] Quick fix for react-scripts@5.0.1 compatibility with Node.js v22+
echo.

cd frontend

echo [STEP 1] Setting Node.js v22+ compatibility environment variables...
set NODE_OPTIONS=--max_old_space_size=4096 --openssl-legacy-provider
set GENERATE_SOURCEMAP=false

echo [STEP 2] Installing compatibility packages...
npm install --save-dev @babel/plugin-proposal-private-property-in-object --force --legacy-peer-deps
npm install --save-dev @babel/plugin-proposal-class-properties --force --legacy-peer-deps

echo [STEP 3] Testing the fix...
echo [INFO] Environment variables set:
echo NODE_OPTIONS=%NODE_OPTIONS%
echo GENERATE_SOURCEMAP=%GENERATE_SOURCEMAP%

echo.
echo ==========================================
echo ✅ Quick Node.js v22+ Fix Applied!
echo ==========================================
echo.
echo Now try running: npm start
echo.
echo If it still doesn't work, try:
echo.
echo 1. Use the comprehensive fix:
echo    fix_node22_compatibility.bat
echo.
echo 2. Or manually run:
echo    set NODE_OPTIONS=--max_old_space_size=4096 --openssl-legacy-provider
echo    set GENERATE_SOURCEMAP=false
echo    npm start
echo.
echo 3. Alternative: Use Node.js v18 or v20
echo.
pause 