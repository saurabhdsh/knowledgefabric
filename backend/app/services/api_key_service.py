import os
import openai
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class APIKeyService:
    """Service for managing API keys and LLM provider configuration"""
    
    def __init__(self):
        self._providers = {
            "openai": {
                "name": "OpenAI GPT-4",
                "api_key": settings.OPENAI_API_KEY,
                "enabled": True,
                "description": "Advanced reasoning with GPT-4",
                "models": ["gpt-4", "gpt-3.5-turbo"],
                "default_model": "gpt-4"
            },
            "gemini": {
                "name": "Google Gemini",
                "api_key": settings.GEMINI_API_KEY,
                "enabled": False,  # Not implemented yet
                "description": "Google's advanced AI model (coming soon)",
                "models": ["gemini-pro"],
                "default_model": "gemini-pro"
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "api_key": settings.ANTHROPIC_API_KEY,
                "enabled": False,  # Not implemented yet
                "description": "Anthropic's Claude model (coming soon)",
                "models": ["claude-3-sonnet"],
                "default_model": "claude-3-sonnet"
            }
        }
        
        # Initialize OpenAI if API key is available
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize API clients for available providers"""
        try:
            # Initialize OpenAI
            if self._providers["openai"]["api_key"]:
                openai.api_key = self._providers["openai"]["api_key"]
                logger.info("OpenAI API key configured successfully")
            else:
                logger.warning("OpenAI API key not found in environment variables")
                self._providers["openai"]["enabled"] = False
        except Exception as e:
            logger.error(f"Error initializing OpenAI: {e}")
            self._providers["openai"]["enabled"] = False
    
    def get_available_providers(self) -> List[Dict]:
        """Get list of available LLM providers with their status"""
        available = []
        
        for provider_id, provider_info in self._providers.items():
            if provider_info["enabled"]:
                available.append({
                    "id": provider_id,
                    "name": provider_info["name"],
                    "description": provider_info["description"],
                    "models": provider_info["models"],
                    "default_model": provider_info["default_model"],
                    "has_api_key": bool(provider_info["api_key"])
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
        """Check if a provider is available and has API key"""
        if provider_id not in self._providers:
            return False
        
        provider = self._providers[provider_id]
        return provider["enabled"] and bool(provider["api_key"])
    
    def get_default_provider(self) -> str:
        """Get the default LLM provider"""
        # Check if default provider is available
        if self.is_provider_available(settings.DEFAULT_LLM_PROVIDER):
            return settings.DEFAULT_LLM_PROVIDER
        
        # Fallback to first available provider
        available = self.get_available_providers()
        if available:
            return available[0]["id"]
        
        return "openai"  # Default fallback
    
    def validate_api_key(self, provider_id: str) -> Tuple[bool, str]:
        """Validate if an API key is properly configured for a provider"""
        if provider_id not in self._providers:
            return False, f"Unknown provider: {provider_id}"
        
        provider = self._providers[provider_id]
        
        if not provider["enabled"]:
            return False, f"Provider {provider_id} is not enabled"
        
        if not provider["api_key"]:
            return False, f"No API key configured for {provider_id}"
        
        # Additional validation could be added here
        # For now, just check if the key exists and has reasonable length
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
            "providers_with_keys": len([p for p in self._providers.values() if p["enabled"] and p["api_key"]])
        }
        
        # Add individual provider status
        status["provider_details"] = {}
        for provider_id, provider_info in self._providers.items():
            is_valid, message = self.validate_api_key(provider_id)
            status["provider_details"][provider_id] = {
                "enabled": provider_info["enabled"],
                "has_api_key": bool(provider_info["api_key"]),
                "is_valid": is_valid,
                "message": message
            }
        
        return status
    
    def update_api_key(self, provider_id: str, api_key: str) -> bool:
        """Update API key for a provider (for runtime configuration)"""
        if provider_id not in self._providers:
            return False
        
        self._providers[provider_id]["api_key"] = api_key
        
        # Re-initialize if this is OpenAI
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