# Knowledge Fabric - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available
- Internet connection for downloading models

### Step 1: Clone and Setup

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd Knowledge-Fabric

# Make setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

### Step 2: Access the Application

Once the setup is complete, you can access:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Step 3: Upload Your First Document

1. Open http://localhost:3000 in your browser
2. Navigate to the "Upload" section
3. Upload a PDF or text file
4. Add a description and tags
5. Click "Upload"

### Step 4: Search Your Knowledge

1. Go to the "Search" section
2. Enter your query
3. View relevant results from your uploaded documents

### Step 5: Connect a Database (Optional)

1. Go to the "Database" section
2. Enter your database connection details
3. Select tables to import
4. Click "Connect"

### Step 6: Train Your Model (Optional)

1. Go to the "Training" section
2. Configure training parameters
3. Start training
4. Monitor progress

## 📁 Project Structure

```
Knowledge-Fabric/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Configuration
│   │   ├── models/         # Data models
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utilities
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   └── utils/          # Utilities
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml      # Multi-container setup
├── setup.sh               # Setup script
└── README.md
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
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
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Training
BATCH_SIZE=32
LEARNING_RATE=2e-5
NUM_EPOCHS=3
```

## 📚 Usage Examples

### Upload a PDF

```bash
curl -X POST "http://localhost:8000/api/v1/upload/pdf" \
  -F "file=@document.pdf" \
  -F "description=Technical documentation" \
  -F "tags=technical,documentation"
```

### Search Knowledge

```bash
curl -X POST "http://localhost:8000/api/v1/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "limit": 5
  }'
```

### Connect Database

```bash
curl -X POST "http://localhost:8000/api/v1/database/connect" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "localhost",
    "port": 5432,
    "database": "postgresql",
    "username": "user",
    "password": "password",
    "table_name": "products"
  }'
```

### Train Model

```bash
curl -X POST "http://localhost:8000/api/v1/training/start" \
  -H "Content-Type: application/json" \
  -d '{
    "epochs": 3,
    "learning_rate": 2e-5,
    "batch_size": 32
  }'
```

## 🛠️ Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm start
```

### Docker Development

```bash
# Start services in development mode
docker-compose up --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🔍 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   lsof -i :8000
   lsof -i :3000
   
   # Kill the process or change ports in docker-compose.yml
   ```

2. **Docker Build Fails**
   ```bash
   # Clean Docker cache
   docker system prune -a
   
   # Rebuild
   docker-compose up --build
   ```

3. **Model Download Fails**
   ```bash
   # Check internet connection
   # The model will be downloaded on first use
   # This may take a few minutes
   ```

4. **Memory Issues**
   ```bash
   # Increase Docker memory limit
   # Or reduce batch_size in .env
   ```

### Debug Commands

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Access container shell
docker-compose exec backend bash
docker-compose exec frontend sh

# Check API health
curl http://localhost:8000/health

# Check frontend
curl http://localhost:3000
```

## 📊 Monitoring

### Health Checks

- Backend: http://localhost:8000/health
- Frontend: http://localhost:3000

### Statistics

- Search stats: `GET /api/v1/search/statistics`
- Knowledge stats: `GET /api/v1/knowledge/statistics`
- Training status: `GET /api/v1/training/status`

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 🔒 Security

### Production Deployment

1. **Change default secrets**
   ```env
   SECRET_KEY=your-very-secure-secret-key
   ```

2. **Enable authentication**
   - Implement JWT authentication
   - Add rate limiting
   - Use HTTPS

3. **Secure file uploads**
   - Validate file types
   - Scan for malware
   - Limit file sizes

4. **Database security**
   - Use encrypted connections
   - Secure credentials
   - Regular backups

## 📈 Performance

### Optimization Tips

1. **Increase Resources**
   - Allocate more RAM to Docker
   - Use SSD storage for vector database

2. **Model Optimization**
   - Use smaller models for faster inference
   - Cache embeddings
   - Batch processing

3. **Search Optimization**
   - Adjust similarity thresholds
   - Use appropriate limits
   - Implement caching

## 🚀 Next Steps

1. **Upload Documents**: Start with PDFs and text files
2. **Connect Databases**: Import structured data
3. **Train Models**: Improve search accuracy
4. **Build Agents**: Integrate with your AI agents
5. **Scale Up**: Add more resources as needed

## 📞 Support

- **Documentation**: Check README.md and API_DOCUMENTATION.md
- **Issues**: Create an issue in the repository
- **Community**: Join our community discussions

## 🎯 Use Cases

### For AI Agents

```python
import requests

# Search knowledge fabric
response = requests.post(
    'http://localhost:8000/api/v1/search/',
    json={
        'query': 'How to implement authentication?',
        'limit': 3
    }
)

# Use results in your agent
results = response.json()['data']['results']
for result in results:
    print(f"Found: {result['content'][:100]}...")
```

### For Applications

```javascript
// Search from your application
const searchKnowledge = async (query) => {
  const response = await fetch('http://localhost:8000/api/v1/search/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit: 5 })
  });
  return response.json();
};
```

## 🎉 Congratulations!

You now have a fully functional Knowledge Fabric system running! 

- Upload documents and build your knowledge base
- Search through your knowledge with semantic understanding
- Connect to databases for comprehensive data access
- Train custom models for domain-specific understanding
- Integrate with your AI agents and applications

Happy building! 🚀 