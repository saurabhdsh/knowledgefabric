"""Provider-agnostic LLM router (OpenAI + AWS Bedrock)."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.llm.bedrock_client import bedrock_client

logger = logging.getLogger(__name__)

_CREDENTIAL_HINTS = (
    "unable to locate credentials",
    "nocredentialserror",
    "credentials not found",
    "could not find credentials",
    "expiredtoken",
    "invalidclienttokenid",
    "the security token included in the request is invalid",
)


class LLMRouter:
    def resolve_provider(self, provider: Optional[str] = None) -> str:
        chosen = (provider or settings.DEFAULT_LLM_PROVIDER or "openai").strip().lower()
        if self.is_provider_ready(chosen):
            return chosen
        for fallback in ("openai", "bedrock"):
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
            if not settings.BEDROCK_ENABLED or not settings.BEDROCK_MODEL_ID:
                return False, "Bedrock is not enabled. Set BEDROCK_ENABLED=true and BEDROCK_MODEL_ID."
            if not bedrock_client.has_aws_credentials():
                return (
                    False,
                    "Bedrock enabled but AWS credentials are missing on this machine. "
                    "Use aws configure / IAM role, or switch to OpenAI.",
                )
            return True, "Bedrock is configured"
        if provider == "openai":
            from app.services.api_key_service import api_key_service

            return api_key_service.validate_api_key("openai")
        return False, f"Unknown or unsupported provider: {provider}"

    @staticmethod
    def _looks_like_credential_error(exc: BaseException) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        return any(hint in text for hint in _CREDENTIAL_HINTS)

    def _openai_completion(
        self,
        *,
        messages: List[Dict[str, str]],
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        api_key: Optional[str],
    ) -> str:
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
            try:
                return bedrock_client.chat_completion(
                    messages,
                    model=bedrock_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                # OpenAI Mac with Bedrock flags but no AWS creds → use OpenAI.
                if self._looks_like_credential_error(exc) and self.is_provider_ready("openai"):
                    logger.warning(
                        "Bedrock failed (%s); falling back to OpenAI",
                        exc,
                    )
                    return self._openai_completion(
                        messages=messages,
                        model=None if (model and model.startswith(bedrock_prefixes)) else model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        api_key=api_key,
                    )
                raise

        if chosen == "openai":
            return self._openai_completion(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key,
            )

        raise RuntimeError(f"Unsupported LLM provider: {chosen}")


llm_router = LLMRouter()
