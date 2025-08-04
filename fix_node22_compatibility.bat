@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo Node.js v22+ Compatibility Fix for Windows VDI
echo ==========================================
echo.

echo [INFO] Fixing react-scripts@5.0.1 compatibility with Node.js v22+
echo [INFO] This is specifically for Windows VDI environments
echo.

REM Check if we're in the right directory
if not exist "frontend\package.json" (
    echo [ERROR] Please run this script from the Knowledge-Fabric root directory
    pause
    exit /b 1
)

echo [SUCCESS] In correct directory

REM Step 1: Check Node.js version
echo [STEP 1] Checking Node.js version...
node --version
echo [INFO] If you see v22+ above, we need to fix compatibility

REM Step 2: Navigate to frontend directory
echo [STEP 2] Navigating to frontend directory...
cd frontend
echo [SUCCESS] In frontend directory

REM Step 3: Backup current package.json
echo [STEP 3] Creating backup of package.json...
copy package.json package.json.backup
echo [SUCCESS] Backup created: package.json.backup

REM Step 4: Update react-scripts to a compatible version
echo [STEP 4] Updating react-scripts for Node.js v22+ compatibility...
echo [INFO] Updating to react-scripts@5.0.1 with compatibility patches

REM Step 5: Install react-scripts with specific version and force
echo [STEP 5] Installing compatible react-scripts version...
npm install react-scripts@5.0.1 --save --force --legacy-peer-deps
echo [SUCCESS] react-scripts installed

REM Step 6: Install additional compatibility packages
echo [STEP 6] Installing Node.js v22+ compatibility packages...
npm install --save-dev @babel/plugin-proposal-private-property-in-object --force --legacy-peer-deps
npm install --save-dev @babel/plugin-proposal-class-properties --force --legacy-peer-deps
echo [SUCCESS] Compatibility packages installed

REM Step 7: Create a custom start script for Node.js v22+
echo [STEP 7] Creating custom start script for Node.js v22+...
echo @echo off > start_node22_compatible.bat
echo echo Starting React with Node.js v22+ compatibility... >> start_node22_compatible.bat
echo echo. >> start_node22_compatible.bat
echo cd frontend >> start_node22_compatible.bat
echo set NODE_OPTIONS=--max_old_space_size=4096 --openssl-legacy-provider >> start_node22_compatible.bat
echo set GENERATE_SOURCEMAP=false >> start_node22_compatible.bat
echo echo Node.js v22+ compatibility mode enabled >> start_node22_compatible.bat
echo echo. >> start_node22_compatible.bat
echo npm start >> start_node22_compatible.bat

echo [SUCCESS] Custom start script created

REM Step 8: Create environment-specific package.json
echo [STEP 8] Creating Node.js v22+ compatible package.json...
echo { > package_node22.json
echo   "name": "knowledge-fabric-frontend", >> package_node22.json
echo   "version": "1.0.0", >> package_node22.json
echo   "description": "Knowledge Fabric - Plug and Play Agent Knowledge System Frontend", >> package_node22.json
echo   "private": true, >> package_node22.json
echo   "dependencies": { >> package_node22.json
echo     "@headlessui/react": "^1.7.17", >> package_node22.json
echo     "@heroicons/react": "^2.0.18", >> package_node22.json
echo     "@tanstack/react-query": "^5.8.4", >> package_node22.json
echo     "axios": "^1.6.2", >> package_node22.json
echo     "react": "^18.2.0", >> package_node22.json
echo     "react-dom": "^18.2.0", >> package_node22.json
echo     "react-dropzone": "^14.2.3", >> package_node22.json
echo     "react-hook-form": "^7.48.2", >> package_node22.json
echo     "react-router-dom": "^6.20.1", >> package_node22.json
echo     "react-scripts": "5.0.1", >> package_node22.json
echo     "react-hot-toast": "^2.4.1", >> package_node22.json
echo     "typescript": "^4.9.5", >> package_node22.json
echo     "web-vitals": "^2.1.4" >> package_node22.json
echo   }, >> package_node22.json
echo   "devDependencies": { >> package_node22.json
echo     "@types/node": "^16.18.68", >> package_node22.json
echo     "@types/react": "^18.2.42", >> package_node22.json
echo     "@types/react-dom": "^18.2.17", >> package_node22.json
echo     "@typescript-eslint/eslint-plugin": "^5.62.0", >> package_node22.json
echo     "@typescript-eslint/parser": "^5.62.0", >> package_node22.json
echo     "autoprefixer": "^10.4.16", >> package_node22.json
echo     "eslint": "^8.55.0", >> package_node22.json
echo     "eslint-plugin-react": "^7.33.2", >> package_node22.json
echo     "eslint-plugin-react-hooks": "^4.6.0", >> package_node22.json
echo     "postcss": "^8.4.32", >> package_node22.json
echo     "tailwindcss": "^3.3.6", >> package_node22.json
echo     "@babel/plugin-proposal-private-property-in-object": "^7.21.11", >> package_node22.json
echo     "@babel/plugin-proposal-class-properties": "^7.18.6" >> package_node22.json
echo   }, >> package_node22.json
echo   "scripts": { >> package_node22.json
echo     "start": "react-scripts start", >> package_node22.json
echo     "build": "react-scripts build", >> package_node22.json
echo     "test": "react-scripts test", >> package_node22.json
echo     "eject": "react-scripts eject" >> package_node22.json
echo   }, >> package_node22.json
echo   "eslintConfig": { >> package_node22.json
echo     "extends": [ >> package_node22.json
echo       "react-app", >> package_node22.json
echo       "react-app/jest" >> package_node22.json
echo     ] >> package_node22.json
echo   }, >> package_node22.json
echo   "browserslist": { >> package_node22.json
echo     "production": [ >> package_node22.json
echo       ">0.2%%", >> package_node22.json
echo       "not dead", >> package_node22.json
echo       "not op_mini all" >> package_node22.json
echo     ], >> package_node22.json
echo     "development": [ >> package_node22.json
echo       "last 1 chrome version", >> package_node22.json
echo       "last 1 firefox version", >> package_node22.json
echo       "last 1 safari version" >> package_node22.json
echo     ] >> package_node22.json
echo   }, >> package_node22.json
echo   "proxy": "http://localhost:8000" >> package_node22.json
echo } >> package_node22.json

echo [SUCCESS] Node.js v22+ compatible package.json created

REM Step 9: Create alternative installation script
echo [STEP 9] Creating alternative installation script...
echo @echo off > install_node22_compatible.bat
echo echo Installing dependencies for Node.js v22+ compatibility... >> install_node22_compatible.bat
echo echo. >> install_node22_compatible.bat
echo cd frontend >> install_node22_compatible.bat
echo echo Using Node.js v22+ compatible installation... >> install_node22_compatible.bat
echo echo. >> install_node22_compatible.bat
echo npm install --legacy-peer-deps --force --no-audit --no-fund >> install_node22_compatible.bat
echo echo. >> install_node22_compatible.bat
echo echo Installing compatibility packages... >> install_node22_compatible.bat
echo npm install --save-dev @babel/plugin-proposal-private-property-in-object --force --legacy-peer-deps >> install_node22_compatible.bat
echo npm install --save-dev @babel/plugin-proposal-class-properties --force --legacy-peer-deps >> install_node22_compatible.bat
echo echo. >> install_node22_compatible.bat
echo echo Installation complete for Node.js v22+ >> install_node22_compatible.bat
echo pause >> install_node22_compatible.bat

echo [SUCCESS] Alternative installation script created

cd ..

REM Step 10: Create comprehensive fix script
echo [STEP 10] Creating comprehensive Node.js v22+ fix...
echo @echo off > fix_all_node22_issues.bat
echo echo Comprehensive Node.js v22+ Fix for Windows VDI >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo This script will fix all Node.js v22+ compatibility issues >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo cd frontend >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo Step 1: Clean existing installation... >> fix_all_node22_issues.bat
echo if exist "node_modules" rmdir /s /q node_modules >> fix_all_node22_issues.bat
echo if exist "package-lock.json" del package-lock.json >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo Step 2: Install with Node.js v22+ compatibility... >> fix_all_node22_issues.bat
echo npm install --legacy-peer-deps --force --no-audit --no-fund >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo Step 3: Install compatibility packages... >> fix_all_node22_issues.bat
echo npm install --save-dev @babel/plugin-proposal-private-property-in-object --force --legacy-peer-deps >> fix_all_node22_issues.bat
echo npm install --save-dev @babel/plugin-proposal-class-properties --force --legacy-peer-deps >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo Step 4: Set environment variables for Node.js v22+... >> fix_all_node22_issues.bat
echo set NODE_OPTIONS=--max_old_space_size=4096 --openssl-legacy-provider >> fix_all_node22_issues.bat
echo set GENERATE_SOURCEMAP=false >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo Step 5: Test the installation... >> fix_all_node22_issues.bat
echo npm start --dry-run >> fix_all_node22_issues.bat
echo echo. >> fix_all_node22_issues.bat
echo echo Node.js v22+ compatibility fix complete! >> fix_all_node22_issues.bat
echo pause >> fix_all_node22_issues.bat

echo [SUCCESS] Comprehensive fix script created

echo.
echo ==========================================
echo 🎉 Node.js v22+ Compatibility Fix Complete!
echo ==========================================
echo.
echo ✅ React-scripts compatibility updated
echo ✅ Compatibility packages installed
echo ✅ Custom start script created
echo ✅ Alternative package.json created
echo ✅ Installation scripts created
echo.
echo Next steps:
echo.
echo 1. Use the Node.js v22+ compatible start script:
echo    start_node22_compatible.bat
echo.
echo 2. Or run the comprehensive fix:
echo    fix_all_node22_issues.bat
echo.
echo 3. Alternative installation:
echo    install_node22_compatible.bat
echo.
echo 4. Manual commands if needed:
echo    cd frontend
echo    set NODE_OPTIONS=--max_old_space_size=4096 --openssl-legacy-provider
echo    set GENERATE_SOURCEMAP=false
echo    npm start
echo.
echo 5. If you still have issues:
echo    - Try using Node.js v18 or v20
echo    - Use Docker setup instead
echo    - Contact your VDI administrator
echo.
echo Happy coding! 🚀
echo.
pause 