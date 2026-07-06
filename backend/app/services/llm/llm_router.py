"""Provider-agnostic LLM router (OpenAI + AWS Bedrock)."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.llm.bedrock_client import bedrock_client

logger = logging.getLogger(__name__)


class LLMRouter:
    def resolve_provider(self, provider: Optional[str] = None) -> str:
        chosen = (provider or settings.DEFAULT_LLM_PROVIDER or "openai").strip().lower()
        if self.is_provider_ready(chosen):
            return chosen
        for fallback in ("bedrock", "openai"):
            if fallback != chosen and self.is_provider_ready(fallback):
                logger.info("LLM provider %s unavailable; falling back to %s", chosen, fallback)
                return fallback
        return chosen

    def ontology_provider(self) -> str:
        return self.resolve_provider(settings.ONTOLOGY_LLM_PROVIDER or settings.DEFAULT_LLM_PROVIDER)

    def is_provider_ready(self, provider: str) -> bool:
        provider = provider.lower()
        if provider == "bedrock":
            return bedrock_client.is_configured()
        if provider == "openai":
            from app.services.api_key_service import api_key_service

            return api_key_service.validate_api_key("openai")[0]
        return False

    def validate_provider(self, provider: str) -> Tuple[bool, str]:
        provider = provider.lower()
        if provider == "bedrock":
            if not bedrock_client.is_configured():
                return False, "Bedrock is not enabled. Set BEDROCK_ENABLED=true and BEDROCK_MODEL_ID."
            return True, "Bedrock is configured"
        if provider == "openai":
            from app.services.api_key_service import api_key_service

            return api_key_service.validate_api_key("openai")
        return False, f"Unknown or unsupported provider: {provider}"

    def chat_completion(
        self,
        *,
        provider: Optional[str] = None,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
        api_key: Optional[str] = None,
    ) -> str:
        chosen = self.resolve_provider(provider)

        if chosen == "bedrock":
            bedrock_prefixes = (
                "anthropic.", "amazon.", "meta.", "cohere.", "ai21.",
                "us.anthropic.", "eu.anthropic.", "global.anthropic.",
                "au.anthropic.", "jp.anthropic.",
            )
            bedrock_model = model if model and model.startswith(bedrock_prefixes) else None
            return bedrock_client.chat_completion(
                messages,
                model=bedrock_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        if chosen == "openai":
            import openai

            openai_model = model or settings.OPENAI_QUERY_MODEL
            kwargs = {
                "model": openai_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if api_key:
                kwargs["api_key"] = api_key
            response = openai.ChatCompletion.create(**kwargs)
            return (response.choices[0].message.content or "").strip()

        raise RuntimeError(f"Unsupported LLM provider: {chosen}")


llm_router = LLMRouter()
