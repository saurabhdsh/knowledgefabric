"""LLM-assisted ontology extraction with structured output and retries."""
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm.llm_router import llm_router

logger = logging.getLogger(__name__)

# Structured schema for LLM output
ONTOLOGY_EXTRACTION_SCHEMA = """
You must respond with a single JSON object (no markdown, no code fence) with exactly these keys:
{
  "entities": [{"name": "string", "normalized_name": "string", "definition": "string or null", "confidence": 0.0-1.0}],
  "relationships": [{"name": "string", "normalized_name": "string", "definition": "string or null", "confidence": 0.0-1.0}],
  "attributes": [{"name": "string", "normalized_name": "string", "data_type_guess": "string or null", "required_flag_guess": false, "confidence": 0.0-1.0}],
  "business_rules": [{"expression": "string", "confidence": 0.0-1.0}]
}
Extract domain entities (nouns/concepts), relationships (verbs/connections), attributes (fields/properties), and business rules (must/required/should/cannot phrases). Be concise. confidence is your certainty 0-1.
"""


class LLMOntologyService:
    """Call LLM to extract ontology candidates from text with validated JSON output."""

    def __init__(self):
        self.model = settings.ONTOLOGY_LLM_MODEL
        self.temperature = settings.ONTOLOGY_LLM_TEMPERATURE
        self.max_retries = settings.ONTOLOGY_MAX_RETRIES

    def is_available(self) -> bool:
        return llm_router.is_provider_ready(llm_router.ontology_provider())

    def _ontology_model(self) -> str | None:
        provider = llm_router.ontology_provider()
        if provider == "bedrock":
            return settings.BEDROCK_ONTOLOGY_MODEL_ID or settings.BEDROCK_MODEL_ID
        return settings.ONTOLOGY_LLM_MODEL

    def extract_from_chunk(self, text_chunk: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Call LLM and parse structured ontology candidates. Returns None on failure."""
        if not self.is_available():
            return None

        user_content = f"Context (optional): {context or 'None'}\n\nText to analyze:\n{text_chunk[:6000]}"
        for attempt in range(self.max_retries):
            try:
                raw = llm_router.chat_completion(
                    provider=llm_router.ontology_provider(),
                    messages=[
                        {"role": "system", "content": ONTOLOGY_EXTRACTION_SCHEMA},
                        {"role": "user", "content": user_content},
                    ],
                    model=self._ontology_model(),
                    max_tokens=2000,
                    temperature=self.temperature,
                )
                parsed = self._parse_json_response(raw)
                if parsed:
                    return self._normalize_llm_output(parsed)
            except Exception as e:
                logger.debug("LLM attempt %s failed: %s", attempt + 1, e)
        return None

    def chat(
        self,
        user_message: str,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """Send a chat message with context and optional history. Returns assistant reply or None."""
        if not self.is_available():
            return None
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history[-4:]:
                role = h.get("role") or "user"
                content = (h.get("content") or "").strip()
                if content and role in ("user", "assistant"):
                    messages.append({"role": role, "content": content[:1500]})
        messages.append({"role": "user", "content": user_message[:1000]})
        try:
            return llm_router.chat_completion(
                provider=llm_router.ontology_provider(),
                messages=messages,
                model=self._ontology_model(),
                max_tokens=400,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning("Ontology chat failed: %s", e)
            return None

    def _parse_json_response(self, raw: str) -> Optional[Dict[str, Any]]:
        """Extract JSON object from raw response (strip markdown if present)."""
        raw = raw.strip()
        # Remove markdown code block
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to find first { ... }
            start = raw.find("{")
            if start >= 0:
                depth = 0
                for i in range(start, len(raw)):
                    if raw[i] == "{":
                        depth += 1
                    elif raw[i] == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(raw[start : i + 1])
                            except json.JSONDecodeError:
                                break
        return None

    def _normalize_llm_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add ids and ensure structure for pipeline."""
        out: Dict[str, List[Dict[str, Any]]] = {
            "entities": [],
            "relationships": [],
            "attributes": [],
            "business_rules": [],
        }
        for e in data.get("entities") or []:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            norm = (e.get("normalized_name") or name).strip().title()
            out["entities"].append({
                "id": f"ent_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "normalized_name": norm,
                "definition": e.get("definition"),
                "confidence": float(e.get("confidence", 0.6)),
                "extraction_source": "llm",
            })
        for r in data.get("relationships") or []:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            norm = (r.get("normalized_name") or name).strip()
            out["relationships"].append({
                "id": f"rel_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "normalized_name": norm,
                "definition": r.get("definition"),
                "confidence": float(r.get("confidence", 0.5)),
                "extraction_source": "llm",
            })
        for a in data.get("attributes") or []:
            name = (a.get("name") or "").strip()
            if not name:
                continue
            norm = (a.get("normalized_name") or name).strip()
            out["attributes"].append({
                "id": f"attr_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "normalized_name": norm,
                "data_type_guess": a.get("data_type_guess"),
                "required_flag_guess": bool(a.get("required_flag_guess", False)),
                "confidence": float(a.get("confidence", 0.5)),
                "extraction_source": "llm",
            })
        for br in data.get("business_rules") or []:
            expr = (br.get("expression") or "").strip()
            if not expr:
                continue
            out["business_rules"].append({
                "id": f"rule_llm_{uuid.uuid4().hex[:8]}",
                "expression": expr[:500],
                "confidence": float(br.get("confidence", 0.5)),
            })
        return out
