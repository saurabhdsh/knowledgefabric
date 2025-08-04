# Manual Setup Steps (When Automated Scripts Fail)

This guide provides step-by-step manual instructions when automated setup scripts end early after Node.js dependencies installation.

## 🚨 When to Use This Guide

Use this manual process when:
- Automated setup scripts end early after Node.js installation
- Scripts fail silently without error messages
- VDI environment restrictions prevent automated setup
- You need complete control over the setup process

## 📋 Prerequisites

Before starting, ensure you have:
- **Python 3.8+** installed
- **Node.js 16+** installed
- **Git** installed
- Write permissions to the current directory

## 🔧 Step-by-Step Manual Process

### **Phase 1: Backend Setup**

#### Step 1: Navigate to Backend Directory
```cmd
cd backend
```

#### Step 2: Create Python Virtual Environment
```cmd
python -m venv venv
```

#### Step 3: Activate Virtual Environment
```cmd
call venv\Scripts\activate.bat
```

#### Step 4: Upgrade pip and Install Build Tools
```cmd
python -m pip install --upgrade pip
python -m pip install --upgrade setuptools wheel
```

#### Step 5: Install Python Dependencies (One by One)
```cmd
# Core packages
python -m pip install fastapi --timeout 300
python -m pip install uvicorn[standard] --timeout 300
python -m pip install pydantic --timeout 300
python -m pip install python-dotenv --timeout 300
python -m pip install aiofiles --timeout 300

# ML packages
python -m pip install numpy --timeout 300
python -m pip install pandas --timeout 300
python -m pip install scikit-learn --timeout 300

# PyTorch (CPU-only for VDI)
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu --timeout 600
python -m pip install transformers --timeout 600
python -m pip install sentence-transformers --timeout 600

# Database packages
python -m pip install chromadb --timeout 300
python -m pip install sqlalchemy --timeout 300
python -m pip install psycopg2-binary --timeout 300
python -m pip install mysql-connector-python --timeout 300

# Remaining packages
python -m pip install pypdf2 --timeout 300
python -m pip install python-jose[cryptography] --timeout 300
python -m pip install passlib[bcrypt] --timeout 300
python -m pip install datasets --timeout 300
python -m pip install accelerate --timeout 300
python -m pip install pyarrow --timeout 300
python -m pip install openai --timeout 300
```

#### Step 6: Verify Backend Dependencies
```cmd
python -c "import fastapi, uvicorn, pydantic; print('Backend dependencies OK')"
```

#### Step 7: Return to Root Directory
```cmd
cd ..
```

### **Phase 2: Frontend Setup**

#### Step 1: Navigate to Frontend Directory
```cmd
cd frontend
```

#### Step 2: Install Node.js Dependencies
```cmd
npm install --timeout=300000
```

#### Step 3: Verify Frontend Dependencies
```cmd
node -e "console.log('Frontend dependencies OK')"
```

#### Step 4: Return to Root Directory
```cmd
cd ..
```

### **Phase 3: Environment Setup**

#### Step 1: Create Environment File
```cmd
# Create basic .env file
echo # Knowledge Fabric Environment Configuration > backend\.env
echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
echo SECRET_KEY=your-secret-key-change-in-production >> backend\.env
echo HOST=0.0.0.0 >> backend\.env
echo PORT=8000 >> backend\.env
echo CHROMA_PERSIST_DIRECTORY=./chroma_db >> backend\.env
echo UPLOAD_DIR=./uploads >> backend\.env
```

#### Step 2: Create Required Directories
```cmd
mkdir backend\uploads
mkdir backend\chroma_db
mkdir backend\models
```

#### Step 3: Create Start Scripts

**Create start_backend.bat:**
```cmd
echo @echo off > start_backend.bat
echo cd backend >> start_backend.bat
echo call venv\Scripts\activate.bat >> start_backend.bat
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> start_backend.bat
```

**Create start_frontend.bat:**
```cmd
echo @echo off > start_frontend.bat
echo cd frontend >> start_frontend.bat
echo npm start >> start_frontend.bat
```

**Create start_all.bat:**
```cmd
echo @echo off > start_all.bat
echo echo Starting Knowledge Fabric... >> start_all.bat
echo echo. >> start_all.bat
echo echo Starting backend... >> start_all.bat
echo cd backend >> start_all.bat
echo call venv\Scripts\activate.bat >> start_all.bat
echo start "Backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" >> start_all.bat
echo cd .. >> start_all.bat
echo echo Starting frontend... >> start_all.bat
echo cd frontend >> start_all.bat
echo start "Frontend" cmd /k "npm start" >> start_all.bat
echo cd .. >> start_all.bat
echo echo. >> start_all.bat
echo echo Knowledge Fabric is starting... >> start_all.bat
echo echo. >> start_all.bat
echo echo Access the application at: >> start_all.bat
echo echo - Frontend: http://localhost:3000 >> start_all.bat
echo echo - Backend API: http://localhost:8000 >> start_all.bat
echo echo - API Docs: http://localhost:8000/docs >> start_all.bat
echo echo. >> start_all.bat
echo pause >> start_all.bat
```

### **Phase 4: Verification**

#### Step 1: Check All Components
```cmd
# Check Python virtual environment
if exist "backend\venv" echo [SUCCESS] Virtual environment exists

# Check Node.js dependencies
if exist "frontend\node_modules" echo [SUCCESS] Node.js dependencies exist

# Check environment file
if exist "backend\.env" echo [SUCCESS] Environment file exists

# Check directories
if exist "backend\uploads" echo [SUCCESS] uploads directory exists
if exist "backend\chroma_db" echo [SUCCESS] chroma_db directory exists
if exist "backend\models" echo [SUCCESS] models directory exists

# Check start scripts
if exist "start_backend.bat" echo [SUCCESS] start_backend.bat exists
if exist "start_frontend.bat" echo [SUCCESS] start_frontend.bat exists
if exist "start_all.bat" echo [SUCCESS] start_all.bat exists
```

#### Step 2: Test Backend
```cmd
cd backend
call venv\Scripts\activate.bat
python -c "import fastapi, uvicorn, pydantic; print('Backend test OK')"
cd ..
```

#### Step 3: Test Frontend
```cmd
cd frontend
node -e "console.log('Frontend test OK')"
cd ..
```

## 🚀 Starting the Application

### **Option 1: Start Both Servers**
```cmd
start_all.bat
```

### **Option 2: Start Servers Separately**

**Terminal 1 - Backend:**
```cmd
cd backend
call venv\Scripts\activate.bat
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```cmd
cd frontend
npm start
```

## ⚙️ Configuration

### **Edit Environment File**
```cmd
notepad backend\.env
```

**Important settings to configure:**
```bash
# Required for OpenAI integration
OPENAI_API_KEY=your-actual-openai-api-key

# Change for production
SECRET_KEY=your-very-secure-secret-key

# Optional: Change ports if needed
PORT=8000
```

## 🔍 Troubleshooting

### **If Backend Fails to Start**
```cmd
# Check if virtual environment is activated
cd backend
call venv\Scripts\activate.bat

# Check if dependencies are installed
python -c "import fastapi, uvicorn, pydantic"

# Check if port 8000 is available
netstat -an | findstr ":8000"
```

### **If Frontend Fails to Start**
```cmd
# Check if Node.js dependencies are installed
cd frontend
dir node_modules

# Clear npm cache and reinstall
npm cache clean --force
rmdir /s node_modules
del package-lock.json
npm install
```

### **If Ports are in Use**
```cmd
# Kill processes using ports
netstat -ano | findstr ":8000"
taskkill /PID <PID_NUMBER> /F

netstat -ano | findstr ":3000"
taskkill /PID <PID_NUMBER> /F
```

## 📋 Manual Setup Checklist

- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] Backend virtual environment created
- [ ] Backend dependencies installed (all packages)
- [ ] Frontend dependencies installed
- [ ] Environment file created
- [ ] Directories created (uploads, chroma_db, models)
- [ ] Start scripts created
- [ ] Backend server starts successfully
- [ ] Frontend server starts successfully
- [ ] Both servers accessible in browser
- [ ] OpenAI API key configured

## 🎯 Quick Manual Commands

**Complete setup in one go:**
```cmd
# Backend
cd backend
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install fastapi uvicorn pydantic python-dotenv aiofiles numpy pandas scikit-learn torch --index-url https://download.pytorch.org/whl/cpu transformers sentence-transformers chromadb sqlalchemy psycopg2-binary mysql-connector-python pypdf2 python-jose[cryptography] passlib[bcrypt] datasets accelerate pyarrow openai

# Frontend
cd ..\frontend
npm install

# Environment
cd ..
echo OPENAI_API_KEY=your-key-here > backend\.env
mkdir backend\uploads backend\chroma_db backend\models

# Start servers
cd backend
call venv\Scripts\activate.bat
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal:
cd frontend
npm start
```

This manual process gives you complete control and helps you understand exactly what's happening at each step! 🚀 