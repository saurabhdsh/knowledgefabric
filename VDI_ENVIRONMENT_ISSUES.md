# VDI Environment Issues After Node.js Dependencies

This guide addresses common issues that occur in VDI environments after Node.js dependencies are installed.

## 🚨 Common VDI Issues After Node.js Installation

### Issue 1: File Permission Errors

**Symptoms:**
- Cannot create directories
- Cannot copy files
- Access denied errors
- File system restrictions

**Solutions:**

#### 1. Use Robust VDI Setup Script
```cmd
# Use the robust VDI setup script
setup_vdi_robust.bat
```

#### 2. Manual Directory Creation
```cmd
# Try creating directories manually
mkdir backend\uploads
mkdir backend\chroma_db
mkdir backend\models

# If that fails, try with different paths
mkdir C:\temp\uploads
mkdir C:\temp\chroma_db
mkdir C:\temp\models
```

#### 3. Check File Permissions
```cmd
# Check if you can write to the current directory
echo test > test_write.txt
if exist test_write.txt (
    echo [SUCCESS] Write permissions OK
    del test_write.txt
) else (
    echo [ERROR] No write permissions
)
```

### Issue 2: Network Command Failures

**Symptoms:**
- `netstat` command fails
- Network commands blocked
- Port checking fails

**Solutions:**

#### 1. Skip Port Checking
```cmd
# Create a setup script that skips port checking
echo @echo off > setup_no_port_check.bat
echo cd backend >> setup_no_port_check.bat
echo call venv\Scripts\activate.bat >> setup_no_port_check.bat
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> setup_no_port_check.bat
```

#### 2. Alternative Port Checking
```cmd
# Use PowerShell instead of netstat
powershell "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue"
powershell "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue"
```

### Issue 3: Environment File Issues

**Symptoms:**
- Cannot copy `env.example`
- File not found errors
- Permission denied

**Solutions:**

#### 1. Create Environment File Manually
```cmd
# Create .env file manually
echo # Knowledge Fabric Environment Configuration > backend\.env
echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
echo SECRET_KEY=your-secret-key-change-in-production >> backend\.env
echo HOST=0.0.0.0 >> backend\.env
echo PORT=8000 >> backend\.env
echo CHROMA_PERSIST_DIRECTORY=./chroma_db >> backend\.env
echo UPLOAD_DIR=./uploads >> backend\.env
```

#### 2. Use Different Location
```cmd
# Create .env in a different location
echo OPENAI_API_KEY=your-openai-api-key-here > C:\temp\.env
echo SECRET_KEY=your-secret-key-change-in-production >> C:\temp\.env
```

### Issue 4: Script Creation Failures

**Symptoms:**
- Cannot create start scripts
- Permission denied errors
- Script files not created

**Solutions:**

#### 1. Create Scripts Manually
```cmd
# Create start_backend.bat manually
echo @echo off > start_backend.bat
echo cd backend >> start_backend.bat
echo call venv\Scripts\activate.bat >> start_backend.bat
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> start_backend.bat

# Create start_frontend.bat manually
echo @echo off > start_frontend.bat
echo cd frontend >> start_frontend.bat
echo npm start >> start_frontend.bat
```

#### 2. Use Different Directory
```cmd
# Create scripts in a different directory
cd C:\temp
echo @echo off > start_backend.bat
echo cd /d C:\path\to\knowledgefabric\backend >> start_backend.bat
echo call venv\Scripts\activate.bat >> start_backend.bat
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> start_backend.bat
```

## 🔧 VDI-Specific Workarounds

### Workaround 1: Minimal Setup
```cmd
# Skip all optional steps and just install dependencies
cd backend
call venv\Scripts\activate.bat
# Dependencies are already installed

cd ..\frontend
# Node.js dependencies are already installed

# Manual steps:
# 1. Create .env file manually
# 2. Create directories manually
# 3. Start servers manually
```

### Workaround 2: Use Different Paths
```cmd
# Use paths that are likely to have write permissions
set BACKEND_DIR=C:\temp\knowledgefabric\backend
set FRONTEND_DIR=C:\temp\knowledgefabric\frontend

# Create virtual environment in temp directory
cd %BACKEND_DIR%
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### Workaround 3: Skip Environment Setup
```cmd
# If environment setup fails, skip it and configure manually
echo [INFO] Skipping environment setup due to VDI restrictions
echo [INFO] Please configure manually:
echo [INFO] 1. Create backend\.env file
echo [INFO] 2. Set OPENAI_API_KEY
echo [INFO] 3. Create directories manually
```

## 🚀 Quick VDI Fix

If everything fails after Node.js installation, try this minimal approach:

```cmd
# 1. Check if dependencies are installed
cd backend
call venv\Scripts\activate.bat
python -c "import fastapi; print('Backend OK')"

cd ..\frontend
node -e "console.log('Frontend OK')"

# 2. Create minimal .env file
echo OPENAI_API_KEY=your-key-here > backend\.env

# 3. Start manually
cd backend
call venv\Scripts\activate.bat
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal:
cd frontend
npm start
```

## 📋 VDI Environment Checklist

- [ ] Python dependencies installed successfully
- [ ] Node.js dependencies installed successfully
- [ ] Virtual environment activated
- [ ] Environment file created or configured
- [ ] Directories created (uploads, chroma_db, models)
- [ ] Start scripts created
- [ ] Ports available (8000, 3000)
- [ ] File permissions adequate
- [ ] Network commands allowed
- [ ] Write permissions to current directory

## 🆘 When All Else Fails

If the setup script fails after Node.js installation:

1. **Check what actually worked:**
   ```cmd
   # Verify Python dependencies
   cd backend
   call venv\Scripts\activate.bat
   python -c "import fastapi, uvicorn, pydantic; print('Python OK')"
   
   # Verify Node.js dependencies
   cd ..\frontend
   node -e "console.log('Node.js OK')"
   ```

2. **Manual configuration:**
   - Create `.env` file manually
   - Create directories manually
   - Start servers manually

3. **Use alternative paths:**
   - Try different directories
   - Use temp directories
   - Check user permissions

4. **Contact VDI administrator:**
   - Request write permissions
   - Ask about network restrictions
   - Inquire about file system limitations 