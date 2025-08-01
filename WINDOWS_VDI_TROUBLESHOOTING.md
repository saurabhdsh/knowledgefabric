# Windows VDI Troubleshooting Guide

This guide addresses common issues when running Knowledge-Fabric on Windows VDI environments.

## 🚨 Common Error: Pip Installation Issues

### Error: `pip._internal.cli.base_command.py` Resolution Error

**Symptoms:**
- Long error traceback during `pip install -r requirements.txt`
- Dependency resolution failures
- Network timeout errors

**Solutions:**

#### 1. Use the Fixed Setup Script
```cmd
# Use the improved setup script
setup_without_docker_fixed.bat
```

#### 2. Manual Step-by-Step Installation
```cmd
cd backend
python -m venv venv
call venv\Scripts\activate.bat

# Upgrade pip first
pip install --upgrade pip --timeout 300

# Install packages individually
pip install fastapi==0.104.1 --timeout 300
pip install uvicorn[standard]==0.24.0 --timeout 300
pip install pydantic==2.5.0 --timeout 300
pip install python-dotenv==1.0.0 --timeout 300
pip install aiofiles==23.2.1 --timeout 300
pip install numpy==1.24.3 --timeout 300
pip install pandas==2.0.3 --timeout 300
pip install scikit-learn==1.3.0 --timeout 300
pip install torch==2.1.0 --timeout 600
pip install transformers==4.35.0 --timeout 600
pip install sentence-transformers==2.2.2 --timeout 600
pip install chromadb==0.4.15 --timeout 300
pip install sqlalchemy==2.0.23 --timeout 300
pip install pypdf2==3.0.1 --timeout 300
pip install openai==0.28.1 --timeout 300
```

#### 3. Network Proxy Issues
If you're behind a corporate firewall:

```cmd
# Set proxy if needed
set HTTP_PROXY=http://proxy.company.com:8080
set HTTPS_PROXY=http://proxy.company.com:8080

# Or use pip with proxy
pip install --proxy http://proxy.company.com:8080 package_name
```

#### 4. Use Alternative Package Index
```cmd
# Use a different PyPI mirror
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ package_name

# Or use conda-forge
conda install -c conda-forge package_name
```

## 🔧 Alternative Installation Methods

### Method 1: Use Conda (Recommended for VDI)
```cmd
# Install Miniconda first
# Download from: https://docs.conda.io/en/latest/miniconda.html

# Create conda environment
conda create -n knowledge-fabric python=3.9
conda activate knowledge-fabric

# Install packages via conda
conda install -c conda-forge fastapi uvicorn pydantic numpy pandas scikit-learn
conda install -c conda-forge pytorch transformers -c pytorch
pip install sentence-transformers chromadb openai
```

### Method 2: Use pip with --no-deps
```cmd
# Install packages without dependencies first
pip install --no-deps torch==2.1.0
pip install --no-deps transformers==4.35.0
pip install sentence-transformers==2.2.2

# Then install remaining packages
pip install fastapi uvicorn pydantic python-dotenv
```

### Method 3: Use Virtual Environment with --user
```cmd
# Install packages to user directory
pip install --user fastapi uvicorn pydantic
pip install --user torch transformers sentence-transformers
```

## 🌐 Network and Firewall Issues

### Check Network Connectivity
```cmd
# Test internet connection
ping google.com

# Test pip connectivity
pip install --dry-run fastapi

# Check if ports are blocked
telnet pypi.org 443
```

### Corporate Firewall Solutions
```cmd
# Use corporate proxy
pip install --proxy http://proxy.company.com:8080 package_name

# Or configure pip.conf
# Create file: %APPDATA%\pip\pip.ini
[global]
proxy = http://proxy.company.com:8080
```

## 💾 Disk Space Issues

### Check Available Space
```cmd
# Check disk space
dir C:\

# Clean pip cache
pip cache purge

# Clean temporary files
del /s /q %TEMP%\*
```

### Use Different Drive
```cmd
# Create virtual environment on different drive
D:
mkdir D:\knowledge-fabric-env
python -m venv D:\knowledge-fabric-env\venv
D:\knowledge-fabric-env\venv\Scripts\activate.bat
```

## 🔄 Python Version Issues

### Check Python Version
```cmd
python --version
python -c "import sys; print(sys.version)"
```

### Install Specific Python Version
```cmd
# Download Python 3.9 from python.org
# Make sure to check "Add to PATH"

# Or use py launcher
py -3.9 -m venv venv
py -3.9 -m pip install package_name
```

## 🚀 Performance Optimizations for VDI

### Reduce Memory Usage
```cmd
# Set environment variables
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
set OMP_NUM_THREADS=2

# Use smaller model
# Edit backend\.env
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
BATCH_SIZE=16
```

### Use CPU-Only PyTorch
```cmd
# Uninstall GPU version
pip uninstall torch

# Install CPU-only version
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 🛠️ Manual Installation Steps

If automated scripts fail, try this manual approach:

### Step 1: Clean Environment
```cmd
# Remove existing virtual environment
rmdir /s backend\venv

# Clear pip cache
pip cache purge
```

### Step 2: Create Fresh Environment
```cmd
cd backend
python -m venv venv
call venv\Scripts\activate.bat
pip install --upgrade pip
```

### Step 3: Install Core Dependencies
```cmd
# Install essential packages first
pip install fastapi uvicorn pydantic python-dotenv aiofiles
pip install numpy pandas scikit-learn
```

### Step 4: Install ML Dependencies
```cmd
# Install PyTorch CPU version
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install transformers
pip install transformers

# Install sentence-transformers
pip install sentence-transformers
```

### Step 5: Install Remaining Packages
```cmd
pip install chromadb sqlalchemy pypdf2 openai
```

## 📞 Getting Help

### Collect Debug Information
```cmd
# Python version
python --version

# Pip version
pip --version

# Network connectivity
ping pypi.org

# Disk space
dir C:\

# Environment variables
echo %PATH%
echo %HTTP_PROXY%
echo %HTTPS_PROXY%
```

### Common Error Messages and Solutions

| Error | Solution |
|-------|----------|
| `Connection timeout` | Use `--timeout 600` or check network |
| `Permission denied` | Run as administrator or use `--user` |
| `Disk space full` | Clean temp files or use different drive |
| `SSL certificate error` | Use `--trusted-host pypi.org` |
| `Package not found` | Check package name or use alternative source |

## 🎯 Quick Fix Commands

```cmd
# If everything fails, try this minimal setup
cd backend
python -m venv venv
call venv\Scripts\activate.bat
pip install fastapi uvicorn pydantic python-dotenv
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers
pip install chromadb openai

cd ..\frontend
npm install
```

This should get you a minimal working version that you can expand later. 