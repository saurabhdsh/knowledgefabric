import openai
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.services.llm.bedrock_client import bedrock_client
import logging

logger = logging.getLogger(__name__)

class APIKeyService:
    """Service for managing API keys and LLM provider configuration"""
    
    def __init__(self):
        self._providers = {
            "openai": {
                "name": "OpenAI GPT-4",
                "api_key": settings.OPENAI_API_KEY,
                "enabled": "openai" in settings.ENABLED_LLM_PROVIDERS,
                "description": "OpenAI direct API (GPT-4)",
                "models": [settings.OPENAI_QUERY_MODEL, "gpt-3.5-turbo"],
                "default_model": settings.OPENAI_QUERY_MODEL,
                "auth_type": "api_key",
            },
            "bedrock": {
                "name": "AWS Bedrock",
                "api_key": None,
                "enabled": "bedrock" in settings.ENABLED_LLM_PROVIDERS and settings.BEDROCK_ENABLED,
                "description": "Enterprise models via AWS Bedrock (IAM auth)",
                "models": [settings.BEDROCK_MODEL_ID],
                "default_model": settings.BEDROCK_MODEL_ID,
                "auth_type": "iam",
            },
            "gemini": {
                "name": "Google Gemini",
                "api_key": settings.GEMINI_API_KEY,
                "enabled": False,
                "description": "Google's advanced AI model (coming soon)",
                "models": ["gemini-pro"],
                "default_model": "gemini-pro",
                "auth_type": "api_key",
            },
            "anthropic": {
                "name": "Anthropic Claude (Direct API)",
                "api_key": settings.ANTHROPIC_API_KEY,
                "enabled": False,
                "description": "Anthropic direct API (coming soon)",
                "models": ["claude-3-sonnet"],
                "default_model": "claude-3-sonnet",
                "auth_type": "api_key",
            }
        }
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize API clients for available providers"""
        try:
            if self._providers["openai"]["api_key"]:
                openai.api_key = self._providers["openai"]["api_key"]
                logger.info("OpenAI API key configured successfully")
            else:
                logger.warning("OpenAI API key not found in environment variables")
                self._providers["openai"]["enabled"] = False
        except Exception as e:
            logger.error(f"Error initializing OpenAI: {e}")
            self._providers["openai"]["enabled"] = False

        if self._providers["bedrock"]["enabled"]:
            if bedrock_client.is_configured():
                logger.info("AWS Bedrock configured (model=%s, region=%s)", settings.BEDROCK_MODEL_ID, settings.AWS_REGION)
            else:
                logger.warning(
                    "Bedrock enabled in config but not ready (missing model/region or AWS credentials); "
                    "OpenAI will be used when available"
                )
                self._providers["bedrock"]["enabled"] = False
    
    def get_available_providers(self) -> List[Dict]:
        """Get list of available LLM providers with their status"""
        available = []
        
        for provider_id, provider_info in self._providers.items():
            is_valid, _ = self.validate_provider(provider_id)
            if provider_info["enabled"] and is_valid:
                available.append({
                    "id": provider_id,
                    "name": provider_info["name"],
                    "description": provider_info["description"],
                    "models": provider_info["models"],
                    "default_model": provider_info["default_model"],
                    "has_api_key": provider_info.get("auth_type") == "api_key" and bool(provider_info["api_key"]),
                    "auth_type": provider_info.get("auth_type", "api_key"),
                })
        
        return available
    
    def get_provider_info(self, provider_id: str) -> Optional[Dict]:
        """Get information about a specific provider"""
        if provider_id in self._providers:
            provider = self._providers[provider_id].copy()
            provider["id"] = provider_id
            return provider
        return None
    
    def is_provider_available(self, provider_id: str) -> bool:
        """Check if a provider is available"""
        return self.validate_provider(provider_id)[0]
    
    def get_default_provider(self) -> str:
        """Get the default LLM provider"""
        if self.is_provider_available(settings.DEFAULT_LLM_PROVIDER):
            return settings.DEFAULT_LLM_PROVIDER
        
        available = self.get_available_providers()
        if available:
            return available[0]["id"]
        
        return settings.DEFAULT_LLM_PROVIDER
    
    def validate_provider(self, provider_id: str) -> Tuple[bool, str]:
        """Validate provider readiness (API key or IAM-backed Bedrock)."""
        if provider_id not in self._providers:
            return False, f"Unknown provider: {provider_id}"

        provider = self._providers[provider_id]
        if not provider["enabled"]:
            return False, f"Provider {provider_id} is not enabled"

        if provider_id == "bedrock":
            if not settings.BEDROCK_ENABLED or not settings.BEDROCK_MODEL_ID:
                return False, "Bedrock is not configured (BEDROCK_ENABLED, BEDROCK_MODEL_ID, AWS_REGION)"
            if not bedrock_client.has_aws_credentials():
                return (
                    False,
                    "Bedrock enabled but AWS credentials are missing; OpenAI will be used if configured",
                )
            return True, "Bedrock is configured via IAM"

        return self.validate_api_key(provider_id)

    def validate_api_key(self, provider_id: str) -> Tuple[bool, str]:
        """Validate if an API key is properly configured for a provider"""
        if provider_id == "bedrock":
            return self.validate_provider("bedrock")

        if provider_id not in self._providers:
            return False, f"Unknown provider: {provider_id}"
        
        provider = self._providers[provider_id]
        
        if not provider["enabled"]:
            return False, f"Provider {provider_id} is not enabled"
        
        if not provider["api_key"]:
            return False, f"No API key configured for {provider_id}"
        
        if len(provider["api_key"]) < 10:
            return False, f"API key for {provider_id} appears to be invalid"
        
        return True, "API key is valid"
    
    def get_api_key(self, provider_id: str) -> Optional[str]:
        """Get the API key for a specific provider"""
        if provider_id in self._providers:
            return self._providers[provider_id]["api_key"]
        return None
    
    def get_provider_status(self) -> Dict:
        """Get overall status of all providers"""
        status = {
            "default_provider": self.get_default_provider(),
            "available_providers": self.get_available_providers(),
            "total_providers": len(self._providers),
            "enabled_providers": len([p for p in self._providers.values() if p["enabled"]]),
            "providers_with_keys": len([
                p for p in self._providers.values()
                if p["enabled"] and (p.get("auth_type") == "iam" or p["api_key"])
            ])
        }
        
        status["provider_details"] = {}
        for provider_id, provider_info in self._providers.items():
            is_valid, message = self.validate_provider(provider_id)
            status["provider_details"][provider_id] = {
                "enabled": provider_info["enabled"],
                "has_api_key": bool(provider_info["api_key"]),
                "auth_type": provider_info.get("auth_type", "api_key"),
                "is_valid": is_valid,
                "message": message
            }
        
        return status
    
    def update_api_key(self, provider_id: str, api_key: str) -> bool:
        """Update API key for a provider (for runtime configuration)"""
        if provider_id not in self._providers:
            return False
        
        self._providers[provider_id]["api_key"] = api_key
        
        if provider_id == "openai":
            try:
                openai.api_key = api_key
                self._providers[provider_id]["enabled"] = True
                logger.info("OpenAI API key updated successfully")
                return True
            except Exception as e:
                logger.error(f"Error updating OpenAI API key: {e}")
                return False
        
        return True

# Global instance
api_key_service = APIKeyService()
