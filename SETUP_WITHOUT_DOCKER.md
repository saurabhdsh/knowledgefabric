# Knowledge Fabric - Setup Without Docker

This guide will help you run the Knowledge-Fabric application on a VDI or any system without Docker.

## 🖥️ System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 18.04+), macOS (10.15+), or Windows 10+
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 10GB free space
- **CPU**: 4 cores minimum (8 cores recommended)

### Software Prerequisites

#### 1. Python 3.8+ Installation

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**macOS:**
```bash
# Using Homebrew
brew install python3

# Or download from python.org
```

**Windows:**
- Download from [python.org](https://www.python.org/downloads/)
- Make sure to check "Add Python to PATH" during installation

#### 2. Node.js 16+ Installation

**Ubuntu/Debian:**
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**macOS:**
```bash
brew install node
```

**Windows:**
- Download from [nodejs.org](https://nodejs.org/)

#### 3. Git Installation

**Ubuntu/Debian:**
```bash
sudo apt install git
```

**macOS:**
```bash
brew install git
```

**Windows:**
- Download from [git-scm.com](https://git-scm.com/)

## 🚀 Installation Steps

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd Knowledge-Fabric
```

### Step 2: Backend Setup

1. **Navigate to backend directory:**
```bash
cd backend
```

2. **Create Python virtual environment:**
```bash
python3 -m venv venv
```

3. **Activate virtual environment:**
```bash
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

4. **Install Python dependencies:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

5. **Create environment file:**
```bash
cp ../env.example .env
```

6. **Edit environment file:**
```bash
# Edit .env file with your configuration
nano .env
```

**Important environment variables to set:**
```bash
# Required for OpenAI integration
OPENAI_API_KEY=your-openai-api-key-here

# Optional: Change secret key for production
SECRET_KEY=your-secret-key-change-in-production

# Optional: Change upload directory
UPLOAD_DIR=./uploads
```

### Step 3: Frontend Setup

1. **Navigate to frontend directory:**
```bash
cd ../frontend
```

2. **Install Node.js dependencies:**
```bash
npm install
```

## 🏃‍♂️ Running the Application

### Option 1: Run Backend and Frontend Separately

#### Start Backend Server
```bash
# Navigate to backend directory
cd backend

# Activate virtual environment (if not already activated)
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Start the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Start Frontend Server
```bash
# Open a new terminal window
# Navigate to frontend directory
cd frontend

# Start the React development server
npm start
```

### Option 2: Use the Setup Script

We've created a setup script to automate the process:

```bash
# Make the script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

## 🌐 Accessing the Application

Once both servers are running:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 📁 Directory Structure After Setup

```
Knowledge-Fabric/
├── backend/
│   ├── venv/                    # Python virtual environment
│   ├── .env                     # Environment configuration
│   ├── uploads/                 # Uploaded files directory
│   ├── chroma_db/              # Vector database
│   └── models/                  # Trained models
├── frontend/
│   ├── node_modules/            # Node.js dependencies
│   └── build/                   # Production build (after npm run build)
└── setup.sh                     # Setup script
```

## 🔧 Configuration

### Backend Configuration (.env file)

Key configuration options:

```bash
# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME=Knowledge Fabric

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Vector Database
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Model Configuration
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# File Upload
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800

# Security
SECRET_KEY=your-secret-key-change-in-production

# OpenAI Integration (Required)
OPENAI_API_KEY=your-openai-api-key-here
```

### Frontend Configuration

The frontend is configured to proxy API requests to the backend at `http://localhost:8000`. This is set in `package.json`:

```json
{
  "proxy": "http://localhost:8000"
}
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Check what's using the port
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill the process or change the port in .env
```

#### 2. Python Dependencies Issues
```bash
# Reinstall dependencies
pip uninstall -r requirements.txt
pip install -r requirements.txt
```

#### 3. Node.js Dependencies Issues
```bash
# Clear npm cache and reinstall
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

#### 4. Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 5. ChromaDB Issues
```bash
# Clear ChromaDB data
rm -rf chroma_db
```

### Performance Optimization

#### For Low-RAM Systems (8GB or less):
1. Reduce batch size in `.env`:
```bash
BATCH_SIZE=16
```

2. Use a smaller model:
```bash
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

3. Limit concurrent uploads in the frontend.

#### For High-Performance Systems:
1. Increase batch size:
```bash
BATCH_SIZE=64
```

2. Use a larger model:
```bash
MODEL_NAME=sentence-transformers/all-mpnet-base-v2
```

## 🔒 Security Considerations

### Production Deployment

1. **Change default secret key:**
```bash
SECRET_KEY=your-very-secure-secret-key-here
```

2. **Use environment variables for sensitive data:**
```bash
export OPENAI_API_KEY=your-api-key
```

3. **Configure firewall rules:**
```bash
# Allow only necessary ports
sudo ufw allow 8000
sudo ufw allow 3000
```

4. **Use HTTPS in production:**
- Set up reverse proxy with Nginx
- Configure SSL certificates

## 📊 Monitoring and Logs

### Backend Logs
```bash
# View backend logs
tail -f backend/logs/app.log
```

### Frontend Logs
```bash
# View frontend logs in browser console
# Or check terminal where npm start is running
```

## 🚀 Production Deployment

### Using PM2 (Node.js Process Manager)

1. **Install PM2:**
```bash
npm install -g pm2
```

2. **Start backend with PM2:**
```bash
cd backend
pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000" --name "knowledge-fabric-backend"
```

3. **Start frontend with PM2:**
```bash
cd frontend
npm run build
pm2 serve build 3000 --name "knowledge-fabric-frontend"
```

4. **Save PM2 configuration:**
```bash
pm2 save
pm2 startup
```

### Using Systemd (Linux)

Create systemd service files for automatic startup on boot.

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the logs for error messages
3. Ensure all prerequisites are installed correctly
4. Verify environment variables are set properly
5. Check that ports 3000 and 8000 are available

For additional support, please open an issue in the repository. 