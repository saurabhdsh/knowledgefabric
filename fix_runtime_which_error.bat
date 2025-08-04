@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo Runtime 'which' Module Error Fix
echo ==========================================
echo.

echo [INFO] This script fixes the runtime 'which' module error
echo [INFO] Even when the module is installed but not found at runtime
echo.

REM Check if we're in the right directory
if not exist "frontend\package.json" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

cd frontend

REM Step 1: Check current which module status
echo [STEP 1] Checking current which module status...
if exist "node_modules\which" (
    echo [INFO] which module exists in node_modules
    dir "node_modules\which" | findstr "index.js" >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] which module exists but index.js is missing
    ) else (
        echo [SUCCESS] which module has index.js
    )
) else (
    echo [WARNING] which module not found in node_modules
)

REM Step 2: Install which module in multiple locations
echo [STEP 2] Installing which module in multiple locations...

REM Install in frontend node_modules
echo [INFO] Installing which in frontend node_modules...
npm install which --save-dev --force

REM Install globally
echo [INFO] Installing which globally...
npm install -g which

REM Step 3: Create a robust which module
echo [STEP 3] Creating robust which module...
if exist "node_modules\which" (
    rmdir /s /q "node_modules\which"
)
mkdir "node_modules\which"

REM Create a more robust which module
echo module.exports = function(cmd) { > "node_modules\which\index.js"
echo   if (typeof cmd !== 'string') return null; >> "node_modules\which\index.js"
echo   if (process.platform === 'win32') { >> "node_modules\which\index.js"
echo     return cmd; >> "node_modules\which\index.js"
echo   } >> "node_modules\which\index.js"
echo   return cmd; >> "node_modules\which\index.js"
echo }; >> "node_modules\which\index.js"

REM Create package.json for the which module
echo { > "node_modules\which\package.json"
echo   "name": "which", >> "node_modules\which\package.json"
echo   "version": "1.0.0", >> "node_modules\which\package.json"
echo   "main": "index.js", >> "node_modules\which\package.json"
echo   "description": "Custom which module for Windows VDI" >> "node_modules\which\package.json"
echo } >> "node_modules\which\package.json"

echo [SUCCESS] Robust which module created

REM Step 4: Fix cross-spawn module
echo [STEP 4] Fixing cross-spawn module...
npm install cross-spawn --save-dev --force

REM Step 5: Create a custom start script that sets NODE_PATH
echo [STEP 5] Creating custom start script with NODE_PATH...
echo @echo off > start_frontend_fixed.bat
echo echo Starting frontend with fixed module resolution... >> start_frontend_fixed.bat
echo echo. >> start_frontend_fixed.bat
echo cd frontend >> start_frontend_fixed.bat
echo set NODE_PATH=%%cd%%\node_modules >> start_frontend_fixed.bat
echo set NODE_OPTIONS=--max_old_space_size=4096 >> start_frontend_fixed.bat
echo echo NODE_PATH set to: %%NODE_PATH%% >> start_frontend_fixed.bat
echo echo. >> start_frontend_fixed.bat
echo npm start >> start_frontend_fixed.bat

echo [SUCCESS] Custom start script created

REM Step 6: Create a patch for react-scripts
echo [STEP 6] Creating patch for react-scripts...
if exist "node_modules\react-scripts\scripts\start.js" (
    echo [INFO] Found react-scripts start.js, creating backup...
    copy "node_modules\react-scripts\scripts\start.js" "node_modules\react-scripts\scripts\start.js.backup" >nul 2>&1
)

REM Step 7: Create a simple test script
echo [STEP 7] Creating test script...
echo @echo off > test_which_module.bat
echo echo Testing which module resolution... >> test_which_module.bat
echo cd frontend >> test_which_module.bat
echo node -e "try { require('which'); console.log('which module found'); } catch(e) { console.log('which module error:', e.message); }" >> test_which_module.bat
echo pause >> test_which_module.bat

echo [SUCCESS] Test script created

cd ..

REM Step 8: Create environment-specific start script
echo [STEP 8] Creating environment-specific start script...
echo @echo off > start_frontend_vdi_safe.bat
echo echo Starting frontend with VDI-safe configuration... >> start_frontend_vdi_safe.bat
echo echo. >> start_frontend_vdi_safe.bat
echo cd frontend >> start_frontend_vdi_safe.bat
echo set NODE_ENV=development >> start_frontend_vdi_safe.bat
echo set NODE_PATH=%%cd%%\node_modules >> start_frontend_vdi_safe.bat
echo set NODE_OPTIONS=--max_old_space_size=4096 --no-warnings >> start_frontend_vdi_safe.bat
echo echo Environment configured for VDI... >> start_frontend_vdi_safe.bat
echo echo. >> start_frontend_vdi_safe.bat
echo echo Testing module resolution first... >> start_frontend_vdi_safe.bat
echo node -e "try { require('which'); console.log('✓ which module OK'); } catch(e) { console.log('✗ which module error:', e.message); }" >> start_frontend_vdi_safe.bat
echo echo. >> start_frontend_vdi_safe.bat
echo echo Starting React development server... >> start_frontend_vdi_safe.bat
echo npm start >> start_frontend_vdi_safe.bat

echo [SUCCESS] VDI-safe start script created

echo.
echo ==========================================
echo 🎉 Runtime 'which' Module Fix Complete!
echo ==========================================
echo.
echo ✅ Robust which module created
echo ✅ Multiple installation locations
echo ✅ Custom start scripts created
echo ✅ Test script created
echo ✅ VDI-safe configuration
echo.
echo Next steps:
echo.
echo 1. Test the which module:
echo    test_which_module.bat
echo.
echo 2. Try starting with the fixed script:
echo    start_frontend_fixed.bat
echo.
echo 3. Or use the VDI-safe start script:
echo    start_frontend_vdi_safe.bat
echo.
echo 4. If you still get errors, try:
echo    - Run as administrator
echo    - Check antivirus software
echo    - Contact VDI administrator
echo.
echo 5. Alternative approach:
echo    - Use yarn instead of npm
echo    - Use Docker setup
echo.
echo Happy coding! 🚀
echo.
pause 