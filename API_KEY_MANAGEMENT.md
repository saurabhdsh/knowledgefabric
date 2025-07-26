# API Key Management System

## Overview

The Knowledge Fabric now includes a comprehensive API key management system that supports multiple LLM providers and follows security best practices.

## 🔐 Security Features

### ✅ **No Hardcoded Keys**
- All API keys are loaded from environment variables
- No API keys are stored in source code
- Secure fallback mechanisms when keys are not available

### ✅ **Multiple Provider Support**
- **OpenAI GPT-4**: Currently implemented and working
- **Google Gemini**: Placeholder for future integration
- **Anthropic Claude**: Placeholder for future integration

### ✅ **Environment Variable Based**
- All configuration through environment variables
- Support for `.env` files
- Docker Compose integration

## 🚀 Quick Setup

### 1. Environment Variables

Create a `.env` file in the root directory:

```bash
# Copy the example file
cp env.example .env

# Edit the file and add your API keys
nano .env
```

### 2. Required API Keys

```bash
# OpenAI (Required for GPT-4 integration)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional - for future integrations
GEMINI_API_KEY=your-gemini-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

### 3. Docker Setup

```bash
# Start with environment variables
docker-compose up --build
```

## 📋 Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 | None | Yes (for OpenAI) |
| `GEMINI_API_KEY` | Google Gemini API key | None | No |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | None | No |
| `DEFAULT_LLM_PROVIDER` | Default LLM provider | `openai` | No |

### Provider Configuration

```python
# Available providers
providers = {
    "openai": {
        "name": "OpenAI GPT-4",
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-4"
    },
    "gemini": {
        "name": "Google Gemini",
        "models": ["gemini-pro"],
        "default_model": "gemini-pro"
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "models": ["claude-3-sonnet"],
        "default_model": "claude-3-sonnet"
    }
}
```

## 🔧 API Endpoints

### Get API Key Status

```bash
curl -X GET "http://localhost:8000/api/v1/knowledge/api-keys/status"
```

**Response:**
```json
{
  "success": true,
  "message": "API key status retrieved successfully",
  "data": {
    "default_provider": "openai",
    "available_providers": [
      {
        "id": "openai",
        "name": "OpenAI GPT-4",
        "description": "Advanced reasoning with GPT-4",
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-4",
        "has_api_key": true
      }
    ],
    "total_providers": 3,
    "enabled_providers": 1,
    "providers_with_keys": 1,
    "provider_details": {
      "openai": {
        "enabled": true,
        "has_api_key": true,
        "is_valid": true,
        "message": "API key is valid"
      },
      "gemini": {
        "enabled": false,
        "has_api_key": false,
        "is_valid": false,
        "message": "No API key configured for gemini"
      }
    }
  }
}
```

### Get Available Providers

```bash
curl -X GET "http://localhost:8000/api/v1/knowledge/api-keys/providers"
```

### Validate API Key

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/api-keys/validate/openai"
```

## 🛠️ Implementation Details

### API Key Service

The system uses a centralized `APIKeyService` class that:

1. **Loads API keys** from environment variables
2. **Validates keys** for proper format and availability
3. **Manages providers** and their status
4. **Provides fallbacks** when keys are not available

### Key Features

- **Automatic Detection**: Detects available providers on startup
- **Validation**: Validates API keys before use
- **Fallback Handling**: Graceful degradation when services unavailable
- **Provider Selection**: Dynamic provider selection based on availability
- **Error Handling**: Comprehensive error handling and logging

### Code Structure

```
backend/app/services/api_key_service.py  # Main API key management
backend/app/core/config.py               # Environment variable configuration
backend/app/api/v1/endpoints/knowledge.py # API endpoints for key management
```

## 🔒 Security Best Practices

### 1. **Environment Variables Only**
```python
# ✅ Good - Load from environment
api_key = os.getenv("OPENAI_API_KEY")

# ❌ Bad - Never hardcode
api_key = "sk-1234567890abcdef"
```

### 2. **Validation**
```python
# Validate API key before use
is_valid, message = api_key_service.validate_api_key("openai")
if not is_valid:
    # Use fallback response
```

### 3. **Error Handling**
```python
try:
    response = openai.ChatCompletion.create(...)
except Exception as e:
    # Log error and use fallback
    logger.error(f"OpenAI API error: {e}")
```

### 4. **No Key Exposure**
- API keys are never returned in API responses
- Keys are not logged in application logs
- Keys are not stored in database

## 🚀 Usage Examples

### Frontend Integration

```typescript
// Get available providers
const response = await fetch('/api/v1/knowledge/api-keys/providers');
const { providers } = await response.json();

// Use available provider
const availableProvider = providers.find(p => p.has_api_key);
```

### Backend Integration

```python
from app.services.api_key_service import api_key_service

# Check if provider is available
if api_key_service.is_provider_available("openai"):
    # Use OpenAI
    response = openai.ChatCompletion.create(...)
else:
    # Use fallback
    response = get_fallback_response()
```

### Docker Deployment

```yaml
# docker-compose.yml
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - GEMINI_API_KEY=${GEMINI_API_KEY}
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

## 🔍 Troubleshooting

### Common Issues

1. **API Key Not Found**
   ```bash
   # Check environment variable
   echo $OPENAI_API_KEY
   
   # Check .env file
   cat .env | grep OPENAI_API_KEY
   ```

2. **Provider Not Available**
   ```bash
   # Check provider status
   curl -X GET "http://localhost:8000/api/v1/knowledge/api-keys/status"
   ```

3. **Docker Environment**
   ```bash
   # Check Docker environment
   docker-compose exec backend env | grep API_KEY
   ```

### Debug Commands

```bash
# Check all environment variables
docker-compose exec backend env

# Check API key service logs
docker-compose logs backend | grep "API Key"

# Test API key validation
curl -X POST "http://localhost:8000/api/v1/knowledge/api-keys/validate/openai"
```

## 🔄 Migration Guide

### From Old System

The new system is backward compatible. No changes needed to existing code.

### Environment Variables

If you have existing environment variables, they will continue to work:

```bash
# Old way (still works)
export OPENAI_API_KEY="your-key"

# New way (recommended)
# Use .env file with all providers
```

## 🎯 Future Enhancements

### Planned Features

1. **Runtime Key Updates**: Update API keys without restart
2. **Key Rotation**: Automatic key rotation support
3. **Usage Monitoring**: Track API key usage and costs
4. **Multi-Key Support**: Support for multiple keys per provider
5. **Key Encryption**: Encrypt API keys at rest

### Provider Integrations

1. **Google Gemini**: Full integration with Gemini Pro
2. **Anthropic Claude**: Full integration with Claude
3. **Local Models**: Support for local LLM models
4. **Custom Providers**: Plugin system for custom providers

## 📚 API Documentation

For complete API documentation, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🤝 Contributing

When adding new LLM providers:

1. Add provider configuration to `APIKeyService`
2. Add environment variable to `Settings`
3. Update Docker Compose configuration
4. Add validation logic
5. Update documentation

## 🔐 Security Checklist

- [ ] No hardcoded API keys in source code
- [ ] All keys loaded from environment variables
- [ ] Proper validation before use
- [ ] Error handling and fallbacks
- [ ] No key exposure in logs or responses
- [ ] Secure Docker configuration
- [ ] Environment file in .gitignore 