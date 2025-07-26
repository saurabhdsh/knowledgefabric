#!/bin/bash

echo "🚀 Knowledge Fabric - Setup Script"
echo "=================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p backend/uploads
mkdir -p backend/chroma_db
mkdir -p backend/models

# Set up environment variables
echo "🔧 Setting up environment variables..."
if [ ! -f .env ]; then
    cat > .env << EOF
# Knowledge Fabric Environment Variables
API_V1_STR=/api/v1
PROJECT_NAME=Knowledge Fabric
HOST=0.0.0.0
PORT=8000
CHROMA_PERSIST_DIRECTORY=./chroma_db
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
BATCH_SIZE=32
LEARNING_RATE=2e-5
NUM_EPOCHS=3

# API Keys Configuration
OPENAI_API_KEY=your-openai-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# LLM Provider Configuration
DEFAULT_LLM_PROVIDER=openai
EOF
    echo "✅ Created .env file"
    echo "⚠️  Please update the API keys in .env file before using LLM features"
else
    echo "✅ .env file already exists"
fi

# Build and start services
echo "🐳 Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check if services are running
echo "🔍 Checking service status..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend API is running"
else
    echo "❌ Backend API is not responding"
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is running"
else
    echo "❌ Frontend is not responding"
fi

echo ""
echo "🎉 Knowledge Fabric is now running!"
echo ""
echo "📱 Access your application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo ""
echo "📚 Next steps:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Upload some PDF documents"
echo "   3. Connect to databases if needed"
echo "   4. Train your BERT model"
echo "   5. Start searching your knowledge fabric!"
echo ""
echo "🛠️ Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop services: docker-compose down"
echo "   Restart services: docker-compose restart"
echo "   Update services: docker-compose up --build -d"
echo ""
echo "📖 For more information, check the README.md file" 