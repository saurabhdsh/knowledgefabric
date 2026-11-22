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

    @staticmethod
    def _clean_key(value: Optional[str]) -> str:
        text = (value or "").strip().strip("\"'[]")
        return "".join(text.split())

    @staticmethod
    def _clean_base(value: Optional[str]) -> str:
        text = (value or "").strip().strip("\"'[]").rstrip("/")
        if not text:
            return "https://api.openai.com/v1"
        lowered = text.lower()
        if "cognitiveservices.azure.com" in lowered or "openai.azure.com" in lowered:
            if not lowered.endswith("/openai/v1"):
                if lowered.endswith("/openai"):
                    text = f"{text}/v1"
                elif "/openai/" not in lowered:
                    text = f"{text}/openai/v1"
        return text

    @staticmethod
    def _openai_model(model: Optional[str]) -> str:
        """Azure hosts one chat deployment. Do not send a public OpenAI model name there."""
        configured = settings.OPENAI_QUERY_MODEL
        base = LLMRouter._clean_base(settings.chat_base_url()).lower()
        if "api.openai.com" not in base:
            return configured
        return model or configured

    @staticmethod
    def _completion_body(
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> Dict:
        body: Dict = {"model": model, "messages": messages}
        # gpt-5 deployments reject temperature and expect max_completion_tokens.
        if model.lower().startswith(("gpt-5", "o1", "o3", "o4")):
            body["max_completion_tokens"] = max(max_tokens, 4096)
            return body
        body["max_tokens"] = max_tokens
        body["temperature"] = temperature
        return body

    @staticmethod
    def _chat_targets(base: str, model: str) -> List[str]:
        targets = [f"{base}/chat/completions"]
        if "azure.com" not in base.lower():
            return targets
        root = base
        for suffix in ("/openai/v1", "/openai"):
            if root.lower().endswith(suffix):
                root = root[: -len(suffix)]
                break
        root = root.rstrip("/")
        for version in ("2024-10-21", "2025-04-01-preview"):
            targets.append(
                f"{root}/openai/deployments/{model}/chat/completions?api-version={version}"
            )
        return targets

    @staticmethod
    def _auth_headers(api_key: str, azure: bool) -> List[Dict[str, str]]:
        # Sending Bearer and api-key together makes this gateway reject the call.
        # Try the subscription key first, then bearer, as separate requests.
        if azure:
            return [
                {"api-key": api_key, "Content-Type": "application/json"},
                {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            ]
        return [{"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}]

    def _post_chat(self, body: Dict, api_key: str) -> str:
        import httpx

        base = self._clean_base(settings.chat_base_url())
        azure = "azure.com" in base.lower()
        if azure and api_key.startswith("sk-"):
            raise RuntimeError(
                "The configured key is an OpenAI platform key. "
                "This VM needs the key from the Azure resource exxondemofdr, "
                "on its Keys and Endpoint page."
            )
        targets = self._chat_targets(base, str(body.get("model") or settings.OPENAI_QUERY_MODEL))
        header_sets = self._auth_headers(api_key, azure)
        last_detail = "Azure rejected the key"
        last_status = 401

        import time

        for url in targets:
            for headers in header_sets:
                payload = dict(body)
                response = None
                for attempt in range(3):
                    response = httpx.post(url, headers=headers, json=payload, timeout=180)
                    if response.status_code < 400:
                        text = self._message_text(response.json())
                        if not text:
                            raise RuntimeError(
                                "Azure OpenAI returned an empty answer. "
                                "The deployment answered, but there was no message text."
                            )
                        return text
                    # Retry rate limits and transient host errors.
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        time.sleep(0.6 * (2 ** attempt))
                        continue
                    break
                detail = (response.text if response is not None else "")[:500]
                last_detail = detail
                last_status = response.status_code if response is not None else 500
                if response is not None and response.status_code == 401:
                    continue
                if "temperature" in detail.lower() and "temperature" in payload:
                    payload.pop("temperature", None)
                    response = httpx.post(url, headers=headers, json=payload, timeout=180)
                    if response.status_code < 400:
                        return self._message_text(response.json())
                    detail = response.text[:500]
                    last_detail = detail
                    last_status = response.status_code
                    if response.status_code == 401:
                        continue
                if "max_tokens" in detail.lower() and "max_tokens" in payload:
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
                    payload.pop("temperature", None)
                    response = httpx.post(url, headers=headers, json=payload, timeout=180)
                    if response.status_code < 400:
                        return self._message_text(response.json())
                    last_detail = response.text[:500]
                    last_status = response.status_code
                    if response.status_code == 401:
                        continue
                if response.status_code in (404, 400):
                    continue
                raise RuntimeError(f"OpenAI chat failed ({response.status_code}): {detail}")

        raise RuntimeError(f"OpenAI chat failed ({last_status}): {last_detail}")

    @staticmethod
    def _message_text(payload: Dict) -> str:
        message = (payload.get("choices") or [{}])[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content).strip()

    def _openai_completion(
        self,
        *,
        messages: List[Dict[str, str]],
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        api_key: Optional[str],
    ) -> str:
        key = self._clean_key(api_key or settings.chat_api_key())
        if not key:
            raise RuntimeError("AZURE_OPENAI_API_KEY is not configured")
        openai_model = self._openai_model(model)
        body = self._completion_body(openai_model, messages, max_tokens, temperature)
        return self._post_chat(body, key)

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
