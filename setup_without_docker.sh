#!/bin/bash

# Knowledge Fabric - Setup Without Docker
# This script automates the setup process for running Knowledge-Fabric without Docker

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check OS
get_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.8+ first."
        exit 1
    fi
    
    # Check Python version
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    required_version="3.8"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        print_error "Python version $python_version is too old. Please install Python 3.8+"
        exit 1
    fi
    
    print_success "Python version $python_version is compatible"
    
    # Create virtual environment
    if [ ! -d "backend/venv" ]; then
        print_status "Creating Python virtual environment..."
        cd backend
        python3 -m venv venv
        cd ..
        print_success "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment and install dependencies
    print_status "Installing Python packages..."
    cd backend
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    pip install -r requirements.txt
    
    cd ..
    print_success "Python dependencies installed"
}

# Function to install Node.js dependencies
install_node_deps() {
    print_status "Installing Node.js dependencies..."
    
    if ! command_exists node; then
        print_error "Node.js is not installed. Please install Node.js 16+ first."
        exit 1
    fi
    
    # Check Node.js version
    node_version=$(node -v | cut -d'v' -f2)
    required_node_version="16.0.0"
    
    if [ "$(printf '%s\n' "$required_node_version" "$node_version" | sort -V | head -n1)" != "$required_node_version" ]; then
        print_error "Node.js version $node_version is too old. Please install Node.js 16+"
        exit 1
    fi
    
    print_success "Node.js version $node_version is compatible"
    
    # Install frontend dependencies
    cd frontend
    npm install
    cd ..
    print_success "Node.js dependencies installed"
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment configuration..."
    
    # Copy environment file if it doesn't exist
    if [ ! -f "backend/.env" ]; then
        cp env.example backend/.env
        print_success "Environment file created"
    else
        print_warning "Environment file already exists"
    fi
    
    # Create necessary directories
    mkdir -p backend/uploads
    mkdir -p backend/chroma_db
    mkdir -p backend/models
    print_success "Directories created"
}

# Function to check ports
check_ports() {
    print_status "Checking if required ports are available..."
    
    # Check port 8000 (backend)
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port 8000 is already in use. Backend may not start properly."
    else
        print_success "Port 8000 is available"
    fi
    
    # Check port 3000 (frontend)
    if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port 3000 is already in use. Frontend may not start properly."
    else
        print_success "Port 3000 is available"
    fi
}

# Function to create start scripts
create_start_scripts() {
    print_status "Creating start scripts..."
    
    # Create backend start script
    cat > start_backend.sh << 'EOF'
#!/bin/bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
    
    # Create frontend start script
    cat > start_frontend.sh << 'EOF'
#!/bin/bash
cd frontend
npm start
EOF
    
    # Create combined start script
    cat > start_all.sh << 'EOF'
#!/bin/bash
# Start both backend and frontend
echo "Starting Knowledge Fabric..."

# Start backend in background
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
cd ../frontend
npm start &
FRONTEND_PID=$!

echo "Knowledge Fabric is starting..."
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Access the application at:"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for user to stop
wait
EOF
    
    # Make scripts executable
    chmod +x start_backend.sh
    chmod +x start_frontend.sh
    chmod +x start_all.sh
    
    print_success "Start scripts created"
}

# Function to display final instructions
show_final_instructions() {
    echo ""
    echo "=========================================="
    echo "🎉 Knowledge Fabric Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Configure your environment:"
    echo "   - Edit backend/.env file"
    echo "   - Set your OPENAI_API_KEY"
    echo "   - Change SECRET_KEY for production"
    echo ""
    echo "2. Start the application:"
    echo "   - Option 1: ./start_all.sh (starts both servers)"
    echo "   - Option 2: ./start_backend.sh (backend only)"
    echo "   - Option 3: ./start_frontend.sh (frontend only)"
    echo ""
    echo "3. Access the application:"
    echo "   - Frontend: http://localhost:3000"
    echo "   - Backend API: http://localhost:8000"
    echo "   - API Documentation: http://localhost:8000/docs"
    echo ""
    echo "4. For production deployment, see SETUP_WITHOUT_DOCKER.md"
    echo ""
    echo "Happy coding! 🚀"
}

# Main setup function
main() {
    echo "=========================================="
    echo "Knowledge Fabric - Setup Without Docker"
    echo "=========================================="
    echo ""
    
    # Check if we're in the right directory
    if [ ! -f "backend/requirements.txt" ] || [ ! -f "frontend/package.json" ]; then
        print_error "Please run this script from the Knowledge-Fabric root directory"
        exit 1
    fi
    
    # Get OS
    OS=$(get_os)
    print_status "Detected OS: $OS"
    
    # Install dependencies
    install_python_deps
    install_node_deps
    
    # Setup environment
    setup_environment
    
    # Check ports
    check_ports
    
    # Create start scripts
    create_start_scripts
    
    # Show final instructions
    show_final_instructions
}

# Run main function
main "$@" 