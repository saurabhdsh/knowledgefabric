"""LLM-assisted ontology extraction with structured output and retries."""
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm.llm_router import llm_router
from app.services.ontology.text_match import (
    canonical_key,
    mentions,
    name_pattern,
    quote_in_text,
    sentence_around,
)

logger = logging.getLogger(__name__)

# Structured schema for LLM output
ONTOLOGY_EXTRACTION_SCHEMA = """
You extract a domain model from the text you are given. Report only what the text states.

Respond with a single JSON object (no markdown, no code fence) with exactly these keys:
{
  "entities": [{"name": "noun as written in the text", "definition": "string or null"}],
  "relationships": [{"subject": "entity name", "predicate": "verb phrase", "object": "entity name", "quote": "one sentence copied word for word from the text"}],
  "attributes": [{"name": "field name as written in the text", "entity": "entity name it belongs to, or null", "data_type_guess": "string or null", "required_flag_guess": false}],
  "business_rules": [{"expression": "one sentence copied word for word from the text", "entity": "entity name or null"}]
}

Rules:
- An entity name must appear in the text.
- A relationship needs a quote: one sentence, copied exactly, that names both the subject and the object. The subject is the one that performs the verb. In "An explanation of benefits is sent to the provider", the subject is "explanation of benefits" and the object is "provider".
- If no single sentence states a relationship, leave it out. Do not infer relationships from general knowledge.
- A business rule is a must / required / cannot / only-if sentence, copied exactly.
- Do not report confidence. Each item is checked against the text after you answer, and anything that is not found there is discarded.
"""

# Confidence comes from what was verified in the text, not from the model.
GROUNDED_ENTITY_CONFIDENCE = 0.7
GROUNDED_RELATIONSHIP_CONFIDENCE = 0.75
GROUNDED_ATTRIBUTE_CONFIDENCE = 0.65
GROUNDED_RULE_CONFIDENCE = 0.8


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

        text_chunk = (text_chunk or "")[:6000]
        user_content = f"Context (optional): {context or 'None'}\n\nText to analyze:\n{text_chunk}"
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
                    return self._normalize_llm_output(parsed, text_chunk)
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

    def _normalize_llm_output(self, data: Dict[str, Any], source_text: str = "") -> Dict[str, Any]:
        """Keep only what the source text states, and score it by what was verified.

        Entities must be named in the text. A relationship needs a quoted
        sentence that is in the text and names both ends. A rule must be a
        sentence from the text. Whatever fails is counted under ``discarded``.
        """
        out: Dict[str, Any] = {
            "entities": [],
            "relationships": [],
            "attributes": [],
            "business_rules": [],
            "discarded": {"entities": 0, "relationships": 0, "attributes": 0, "business_rules": 0},
        }
        discarded = out["discarded"]
        known: Dict[str, str] = {}  # canonical name -> display name

        def keep_entity(name: str, definition: Any = None) -> bool:
            name = (name or "").strip()
            key = canonical_key(name)
            if not key:
                return False
            if key in known:
                return True
            if not mentions(name, source_text):
                return False
            known[key] = name
            out["entities"].append({
                "id": f"ent_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "normalized_name": name.strip().title(),
                "definition": definition,
                "confidence": GROUNDED_ENTITY_CONFIDENCE,
                "evidence_snippet": self._snippet(source_text, name),
                "extraction_source": "llm",
            })
            return True

        for e in data.get("entities") or []:
            if not isinstance(e, dict) or not (e.get("name") or "").strip():
                continue
            if not keep_entity(e.get("name"), e.get("definition")):
                discarded["entities"] += 1

        for r in data.get("relationships") or []:
            if not isinstance(r, dict):
                continue
            subject = (r.get("subject") or "").strip()
            obj = (r.get("object") or "").strip()
            predicate = (r.get("predicate") or r.get("name") or "").strip()
            quote = (r.get("quote") or "").strip()
            grounded = (
                subject and obj and predicate
                and canonical_key(subject) != canonical_key(obj)
                and quote_in_text(quote, source_text)
                and mentions(subject, quote)
                and mentions(obj, quote)
                and keep_entity(subject)
                and keep_entity(obj)
            )
            if not grounded:
                discarded["relationships"] += 1
                continue
            out["relationships"].append({
                "id": f"rel_llm_{uuid.uuid4().hex[:8]}",
                "name": predicate,
                "normalized_name": predicate,
                "predicate": predicate,
                "subject": known[canonical_key(subject)],
                "object": known[canonical_key(obj)],
                "quote": quote[:400],
                "quote_verified": True,
                "evidence_snippet": quote[:400],
                "definition": r.get("definition"),
                "confidence": GROUNDED_RELATIONSHIP_CONFIDENCE,
                "extraction_source": "llm",
            })

        for a in data.get("attributes") or []:
            if not isinstance(a, dict):
                continue
            name = (a.get("name") or "").strip()
            if not name or not mentions(name, source_text):
                if name:
                    discarded["attributes"] += 1
                continue
            owner = (a.get("entity") or "").strip()
            owner_key = canonical_key(owner)
            out["attributes"].append({
                "id": f"attr_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "normalized_name": (a.get("normalized_name") or name).strip(),
                "entity": known.get(owner_key) if owner_key else None,
                "data_type_guess": a.get("data_type_guess"),
                "required_flag_guess": bool(a.get("required_flag_guess", False)),
                "confidence": GROUNDED_ATTRIBUTE_CONFIDENCE,
                "evidence_snippet": self._snippet(source_text, name),
                "extraction_source": "llm",
            })

        for br in data.get("business_rules") or []:
            if not isinstance(br, dict):
                continue
            expr = (br.get("expression") or "").strip()
            if not expr:
                continue
            if not quote_in_text(expr, source_text):
                discarded["business_rules"] += 1
                continue
            owner_key = canonical_key(br.get("entity") or "")
            out["business_rules"].append({
                "id": f"rule_llm_{uuid.uuid4().hex[:8]}",
                "expression": expr[:500],
                "evidence_snippet": expr[:300],
                "related_entity": known.get(owner_key) if owner_key else None,
                "confidence": GROUNDED_RULE_CONFIDENCE,
            })
        return out

    @staticmethod
    def _snippet(text: str, phrase: str, window: int = 160) -> str:
        """The sentence around the first whole-word mention of ``phrase``."""
        pattern = name_pattern(phrase)
        match = pattern.search(text or "") if pattern else None
        if not match:
            return ""
        sentence, _ = sentence_around(text, match.start(), match.end())
        return sentence.strip()[:window]
