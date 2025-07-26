# Knowledge Fabric - Plug and Play Agent Knowledge System

An amazing Plug and Play Knowledge Fabric Creation tool for Agents that provides contextual knowledge access through a beautiful web interface.

## 🚀 Features

- **Multi-Source Knowledge Ingestion**: Upload PDFs, connect databases, or use mixed sources
- **Local Vector Database**: ChromaDB for efficient similarity search
- **Local BERT Model**: Train and use local embeddings for privacy
- **Beautiful React Frontend**: Modern, modular UI with amazing UX
- **Docker Containerization**: Easy deployment and scaling
- **RESTful API**: Clean endpoints for agent integration
- **Real-time Processing**: Stream knowledge creation and updates

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  FastAPI Backend│    │  ChromaDB Vector│
│                 │◄──►│                 │◄──►│     Database    │
│  - Upload UI    │    │  - Knowledge API│    │                 │
│  - Management   │    │  - BERT Training│    │  - Embeddings   │
│  - Search       │    │  - Processing   │    │  - Similarity   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Local BERT     │
                       │     Model       │
                       │                 │
                       │  - Embeddings   │
                       │  - Training     │
                       └─────────────────┘
```

## 📁 Project Structure

```
Knowledge-Fabric/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Core configurations
│   │   ├── models/         # Data models
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utilities
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   └── utils/          # Utilities
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml      # Multi-container setup
└── README.md
```

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern, fast web framework
- **ChromaDB** - Local vector database
- **Sentence Transformers** - BERT-based embeddings
- **PyPDF2** - PDF processing
- **SQLAlchemy** - Database ORM
- **Pydantic** - Data validation

### Frontend
- **React 18** - Modern UI framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling
- **React Query** - Data fetching
- **React Router** - Navigation
- **Axios** - HTTP client

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-service orchestration
- **Nginx** - Reverse proxy

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd Knowledge-Fabric
   ```

2. **Start with Docker**
   ```bash
   docker-compose up --build
   ```

3. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## 📚 Usage

### For Agent Developers

1. **Create Knowledge Fabric**
   - Upload PDFs through the web interface
   - Connect to databases (PostgreSQL, MySQL, etc.)
   - Mix multiple sources for comprehensive knowledge

2. **Train Local Model**
   - Use the built-in BERT model training
   - Customize embeddings for your domain
   - Ensure data privacy with local processing

3. **Access Knowledge via API**
   ```bash
   # Search for contextual knowledge
   curl -X POST "http://localhost:8000/api/v1/search" \
        -H "Content-Type: application/json" \
        -d '{"query": "your question", "limit": 5}'
   ```

### API Endpoints

- `POST /api/v1/upload` - Upload PDF files
- `POST /api/v1/connect-db` - Connect database sources
- `POST /api/v1/search` - Search knowledge fabric
- `GET /api/v1/knowledge` - List all knowledge sources
- `POST /api/v1/train` - Train local BERT model

## 🔧 Development

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

## 🐳 Docker Deployment

```bash
# Build and run all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For support and questions, please open an issue in the repository. 