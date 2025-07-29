# Quick Start - Without Docker

This is a quick guide to get Knowledge-Fabric running without Docker on your VDI or local machine.

## 🚀 Quick Setup (3 Steps)

### Step 1: Prerequisites
Make sure you have installed:
- **Python 3.8+** ([Download](https://www.python.org/downloads/))
- **Node.js 16+** ([Download](https://nodejs.org/))
- **Git** ([Download](https://git-scm.com/))

### Step 2: Automated Setup

**Linux/macOS:**
```bash
chmod +x setup_without_docker.sh
./setup_without_docker.sh
```

**Windows:**
```cmd
setup_without_docker.bat
```

### Step 3: Start the Application

**Option A: Start both servers at once**
```bash
# Linux/macOS
./start_all.sh

# Windows
start_all.bat
```

**Option B: Start servers separately**
```bash
# Terminal 1 - Backend
./start_backend.sh    # Linux/macOS
start_backend.bat     # Windows

# Terminal 2 - Frontend  
./start_frontend.sh   # Linux/macOS
start_frontend.bat    # Windows
```

## 🌐 Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## ⚙️ Configuration

Edit `backend/.env` file to configure:
```bash
# Required for OpenAI integration
OPENAI_API_KEY=your-openai-api-key-here

# Optional: Change for production
SECRET_KEY=your-secret-key-change-in-production
```

## 🛠️ Manual Setup (If Automated Setup Fails)

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp ../env.example .env
# Edit .env file with your settings
```

### Frontend Setup
```bash
cd frontend
npm install
```

### Start Servers
```bash
# Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (new terminal)
cd frontend
npm start
```

## 🔧 Troubleshooting

### Common Issues:

1. **Port already in use**
   ```bash
   # Kill process using port 8000
   lsof -ti:8000 | xargs kill -9  # Linux/macOS
   netstat -ano | findstr :8000   # Windows
   ```

2. **Python dependencies fail**
   ```bash
   cd backend
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Node.js dependencies fail**
   ```bash
   cd frontend
   npm cache clean --force
   rm -rf node_modules package-lock.json
   npm install
   ```

4. **Virtual environment issues**
   ```bash
   cd backend
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## 📋 System Requirements

- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 10GB free space
- **CPU**: 4 cores minimum (8 cores recommended)

## 📚 Full Documentation

For detailed setup instructions, troubleshooting, and production deployment, see:
- `SETUP_WITHOUT_DOCKER.md` - Complete setup guide
- `README.md` - Project overview and features

## 🆘 Need Help?

1. Check the troubleshooting section above
2. Review logs in the terminal where servers are running
3. Ensure all prerequisites are installed correctly
4. Verify environment variables in `backend/.env` 