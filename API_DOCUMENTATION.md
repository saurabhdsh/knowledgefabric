# Knowledge Fabric API Documentation

## Overview

The Knowledge Fabric API provides a comprehensive set of endpoints for managing knowledge sources, searching through documents, training BERT models, and connecting to external databases.

**Base URL:** `http://localhost:8000/api/v1`

## Authentication

Currently, the API runs without authentication for development purposes. In production, implement proper authentication using JWT tokens.

## Response Format

All API responses follow this standard format:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data
  },
  "error": null
}
```

## Endpoints

### 1. Upload Endpoints

#### Upload PDF File
```
POST /upload/pdf
```

**Form Data:**
- `file` (required): PDF file
- `description` (optional): Description of the document
- `tags` (optional): Comma-separated tags

**Response:**
```json
{
  "success": true,
  "message": "PDF uploaded and processed successfully",
  "data": {
    "source_id": "uuid",
    "source_name": "document_name",
    "documents_processed": 15,
    "document_ids": ["id1", "id2", ...],
    "knowledge_source": {
      "id": "uuid",
      "name": "document_name",
      "source_type": "pdf",
      "description": "Document description",
      "tags": ["tag1", "tag2"],
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00",
      "document_count": 15,
      "status": "active"
    }
  }
}
```

#### Upload Text File
```
POST /upload/text
```

**Form Data:**
- `file` (required): Text file (.txt)
- `description` (optional): Description of the document
- `tags` (optional): Comma-separated tags

#### Upload Multiple Files
```
POST /upload/multiple
```

**Form Data:**
- `files` (required): Multiple files
- `description` (optional): Description
- `tags` (optional): Comma-separated tags

### 2. Search Endpoints

#### Search Knowledge
```
POST /search/
```

**Request Body:**
```json
{
  "query": "What is machine learning?",
  "limit": 5,
  "threshold": 0.7,
  "filters": {
    "source_type": "pdf"
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "doc_id",
      "content": "Machine learning is a subset of artificial intelligence...",
      "source": "technical_manual.pdf",
      "similarity_score": 0.85,
      "metadata": {
        "page_number": 1,
        "file_name": "technical_manual.pdf"
      },
      "page_number": 1
    }
  ],
  "total_results": 1,
  "query": "What is machine learning?",
  "processing_time": 0.123
}
```

#### Semantic Search
```
POST /search/semantic
```

**Query Parameters:**
- `query` (required): Search query
- `limit` (optional): Number of results (default: 5)
- `threshold` (optional): Similarity threshold (default: 0.7)
- `context_window` (optional): Context window size (default: 3)

#### Get Search Suggestions
```
GET /search/suggestions?query=machine&limit=5
```

#### Get Search Statistics
```
GET /search/statistics
```

### 3. Knowledge Management Endpoints

#### List Knowledge Sources
```
GET /knowledge/sources
```

**Response:**
```json
{
  "success": true,
  "message": "Found 3 knowledge sources",
  "data": [
    {
      "id": "source_id",
      "name": "Technical Manual",
      "source_type": "pdf",
      "description": "Technical documentation",
      "tags": ["technical", "manual"],
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00",
      "document_count": 15,
      "status": "active"
    }
  ]
}
```

#### Get Knowledge Source Details
```
GET /knowledge/sources/{source_id}
```

#### Delete Knowledge Source
```
DELETE /knowledge/sources/{source_id}
```

#### Get Knowledge Statistics
```
GET /knowledge/statistics
```

#### Get Source Documents
```
GET /knowledge/documents/{source_id}?limit=50&offset=0
```

#### Export Knowledge Source
```
POST /knowledge/export/{source_id}?format=json
```

### 4. Training Endpoints

#### Start Model Training
```
POST /training/start
```

**Request Body:**
```json
{
  "model_name": "custom_model",
  "epochs": 3,
  "learning_rate": 2e-5,
  "batch_size": 32
}
```

#### Get Training Status
```
GET /training/status
```

#### List Available Models
```
GET /training/models
```

#### Load Model
```
POST /training/models/{model_id}/load
```

#### Delete Model
```
DELETE /training/models/{model_id}
```

#### Fine-tune Model
```
POST /training/fine-tune
```

**Request Body:**
```json
{
  "source_ids": ["source1", "source2"],
  "epochs": 3,
  "learning_rate": 2e-5,
  "batch_size": 32
}
```

#### Get Model Performance
```
GET /training/performance
```

#### Evaluate Model
```
POST /training/evaluate
```

**Request Body:**
```json
{
  "test_queries": [
    "What is machine learning?",
    "How does neural networks work?"
  ]
}
```

### 5. Database Connection Endpoints

#### Connect Database
```
POST /database/connect
```

**Request Body:**
```json
{
  "host": "localhost",
  "port": 5432,
  "database": "postgresql",
  "username": "user",
  "password": "password",
  "table_name": "customers",
  "query": "SELECT * FROM customers WHERE active = true"
}
```

#### Test Database Connection
```
POST /database/test-connection
```

#### Get Database Schemas
```
GET /database/schemas
```

#### Preview Database Data
```
GET /database/preview?limit=10
```

#### Sync Database Changes
```
POST /database/sync
```

**Request Body:**
```json
{
  "source_id": "source_id",
  "connection": {
    "host": "localhost",
    "port": 5432,
    "database": "postgresql",
    "username": "user",
    "password": "password",
    "table_name": "customers"
  },
  "sync_interval": 3600
}
```

## Error Handling

The API returns appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request
- `404`: Not Found
- `500`: Internal Server Error

Error responses include:

```json
{
  "success": false,
  "message": "Error description",
  "data": null,
  "error": "Detailed error information"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. For production, consider implementing rate limiting based on your requirements.

## File Upload Limits

- Maximum file size: 50MB
- Supported formats: PDF, TXT
- Multiple file uploads are supported

## Search Parameters

- `limit`: Number of results (1-50, default: 5)
- `threshold`: Similarity threshold (0.0-1.0, default: 0.7)
- `filters`: Optional metadata filters

## Model Training

- Supported models: BERT-based (sentence-transformers)
- Training data: All documents in the knowledge fabric
- Fine-tuning: Available for specific knowledge sources
- Model persistence: Local storage in `/models` directory

## Database Support

- PostgreSQL
- MySQL/MariaDB
- SQLite
- Custom queries supported
- Schema discovery
- Data preview functionality

## Examples

### Upload a PDF and Search

```bash
# Upload PDF
curl -X POST "http://localhost:8000/api/v1/upload/pdf" \
  -F "file=@document.pdf" \
  -F "description=Technical documentation" \
  -F "tags=technical,documentation"

# Search the uploaded content
curl -X POST "http://localhost:8000/api/v1/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic?",
    "limit": 5
  }'
```

### Connect Database and Import Data

```bash
# Connect to PostgreSQL
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
# Start training
curl -X POST "http://localhost:8000/api/v1/training/start" \
  -H "Content-Type: application/json" \
  -d '{
    "epochs": 3,
    "learning_rate": 2e-5,
    "batch_size": 32
  }'

# Check status
curl -X GET "http://localhost:8000/api/v1/training/status"
```

## SDK Examples

### Python

```python
import requests

# Upload PDF
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/upload/pdf',
        files={'file': f},
        data={'description': 'Technical documentation'}
    )

# Search
response = requests.post(
    'http://localhost:8000/api/v1/search/',
    json={
        'query': 'What is machine learning?',
        'limit': 5
    }
)
```

### JavaScript

```javascript
// Upload PDF
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('description', 'Technical documentation');

fetch('http://localhost:8000/api/v1/upload/pdf', {
  method: 'POST',
  body: formData
});

// Search
fetch('http://localhost:8000/api/v1/search/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: 'What is machine learning?',
    limit: 5
  })
});
```

## WebSocket Support

For real-time features like training progress updates, consider implementing WebSocket endpoints in future versions.

## Monitoring and Logging

- Health check endpoint: `GET /health`
- API documentation: `GET /docs` (Swagger UI)
- Alternative docs: `GET /redoc` (ReDoc)

## Security Considerations

1. **File Upload Security**: Validate file types and scan for malware
2. **Database Connections**: Use encrypted connections and secure credentials
3. **API Security**: Implement authentication and authorization
4. **Data Privacy**: Ensure sensitive data is properly handled
5. **Rate Limiting**: Implement to prevent abuse

## Performance Tips

1. **Batch Operations**: Use batch uploads for multiple files
2. **Search Optimization**: Use appropriate thresholds and limits
3. **Model Caching**: Cache trained models for faster inference
4. **Database Indexing**: Index frequently queried fields
5. **Vector Database**: ChromaDB provides efficient similarity search

## Troubleshooting

### Common Issues

1. **File Upload Fails**: Check file size and format
2. **Search Returns No Results**: Lower the similarity threshold
3. **Training Fails**: Ensure sufficient documents are available
4. **Database Connection Fails**: Verify credentials and network access

### Debug Endpoints

- `GET /health`: Check API health
- `GET /search/statistics`: View search statistics
- `GET /knowledge/statistics`: View knowledge fabric statistics
- `GET /training/status`: Check training status

## Support

For issues and questions:
1. Check the logs: `docker-compose logs -f`
2. Verify service health: `docker-compose ps`
3. Restart services: `docker-compose restart`
4. Rebuild if needed: `docker-compose up --build -d` 