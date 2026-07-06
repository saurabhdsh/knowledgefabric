"""AWS Bedrock chat completions via the Converse API."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class BedrockClient:
    def __init__(self) -> None:
        self._client = None

    def _runtime(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=settings.AWS_REGION,
            )
        return self._client

    def is_configured(self) -> bool:
        return bool(settings.BEDROCK_ENABLED and settings.BEDROCK_MODEL_ID and settings.AWS_REGION)

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            import boto3

            boto3.client("bedrock", region_name=settings.AWS_REGION).list_foundation_models(
                byOutputModality="TEXT"
            )
            return True
        except Exception as exc:
            logger.warning("Bedrock availability check failed: %s", exc)
            # IAM / network may block list; still allow converse attempts at runtime.
            return True

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str:
        if not self.is_configured():
            raise RuntimeError("Bedrock is not enabled or BEDROCK_MODEL_ID is missing.")

        model_id = model or settings.BEDROCK_MODEL_ID
        system_blocks: List[Dict[str, str]] = []
        converse_messages: List[Dict[str, Any]] = []

        for msg in messages:
            role = (msg.get("role") or "user").lower()
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system_blocks.append({"text": content})
                continue
            converse_role = "assistant" if role == "assistant" else "user"
            converse_messages.append(
                {
                    "role": converse_role,
                    "content": [{"text": content}],
                }
            )

        if not converse_messages:
            raise ValueError("At least one user/assistant message is required.")

        kwargs: Dict[str, Any] = {
            "modelId": model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        response = self._runtime().converse(**kwargs)
        parts = response.get("output", {}).get("message", {}).get("content") or []
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        text = "\n".join(text_parts).strip()
        if not text:
            raise RuntimeError("Bedrock returned an empty response.")
        return text


bedrock_client = BedrockClient()
