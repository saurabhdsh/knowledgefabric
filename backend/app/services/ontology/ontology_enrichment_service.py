"""AI-assisted ontology enrichment engine with deterministic fallback."""
from __future__ import annotations

import re
import uuid
import json
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.llm.llm_router import llm_router
from app.models.ontology import (
    ChangeStatus,
    ChangeType,
    DomainClass,
    GovernanceMode,
    OntologyChangeCandidate,
    RecommendationType,
    RiskLevel,
    SensitivityClass,
)
from app.services.ontology.ontology_persistence_service import OntologyPersistenceService


SENSITIVE_KEYWORDS = {
    SensitivityClass.PII: ["name", "email", "phone", "address", "ssn", "member_id", "subscriber_id", "dob"],
    SensitivityClass.PHI: ["diagnosis", "icd", "procedure", "clinical", "medication", "care_gap", "patient"],
    SensitivityClass.FINANCIAL: ["amount", "charge", "payment", "balance", "premium", "copay", "deductible", "claim"],
    SensitivityClass.REGULATORY: ["policy", "authorization", "compliance", "consent", "audit"],
}

DOMAIN_KEYWORDS = {
    DomainClass.MEMBER: ["member", "subscriber", "enrollee", "beneficiary"],
    DomainClass.PROVIDER: ["provider", "practitioner", "npi", "facility"],
    DomainClass.CLAIM: ["claim", "adjudication", "remit", "payment"],
    DomainClass.POLICY: ["policy", "plan", "coverage"],
    DomainClass.AUTHORIZATION: ["auth", "authorization", "preauth"],
    DomainClass.DIAGNOSIS: ["diagnosis", "icd", "condition"],
    DomainClass.PROCEDURE: ["procedure", "cpt", "hcpcs"],
    DomainClass.MEDICATION: ["medication", "drug", "rx", "ndc"],
    DomainClass.CARE_MANAGEMENT: ["care_gap", "care", "risk_score", "priority"],
    DomainClass.FINANCE: ["finance", "amount", "cost", "premium", "invoice"],
}

SYNONYM_MAP = {
    "subscriber_id": ["member_id", "member_identifier", "subscriber_identifier"],
    "member_id": ["subscriber_id", "beneficiary_id"],
    "provider_risk_tier": ["provider_tier", "risk_tier"],
}


class OntologyEnrichmentService:
    def __init__(self, persistence: Optional[OntologyPersistenceService] = None):
        self.persistence = persistence or OntologyPersistenceService()

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

    def _infer_type(self, field: Dict[str, Any]) -> str:
        explicit = str(field.get("type") or "").strip().lower()
        if explicit:
            return explicit
        values = field.get("sample_values") or []
        if not values:
            return "string"
        nums = 0
        for v in values:
            try:
                float(str(v))
                nums += 1
            except Exception:
                pass
        if nums == len(values):
            return "number"
        return "string"

    def _detect_domain(self, normalized: str) -> DomainClass:
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(k in normalized for k in keywords):
                return domain
        return DomainClass.GENERIC

    def _detect_sensitivity(self, normalized: str) -> SensitivityClass:
        for sensitivity, keywords in SENSITIVE_KEYWORDS.items():
            if any(k in normalized for k in keywords):
                return sensitivity
        return SensitivityClass.NON_SENSITIVE

    def _similarity(self, field_name: str, existing_name: str) -> float:
        a = self._normalize_name(field_name)
        b = self._normalize_name(existing_name)
        exact = 1.0 if a == b else 0.0
        synonym = 1.0 if (a in SYNONYM_MAP and b in SYNONYM_MAP[a]) or (b in SYNONYM_MAP and a in SYNONYM_MAP[b]) else 0.0
        seq = SequenceMatcher(None, a, b).ratio()
        return max(exact, synonym * 0.95, seq)

    def _find_best_match(self, field_name: str, ontology_attributes: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], float]:
        best = None
        score = 0.0
        for attr in ontology_attributes:
            existing = attr.get("name") or attr.get("attribute_name") or ""
            s = self._similarity(field_name, existing)
            if s > score:
                score = s
                best = attr
        return best, score

    def _policy_decision(self, candidate: OntologyChangeCandidate, governance_mode: GovernanceMode) -> Tuple[RecommendationType, str]:
        if governance_mode == GovernanceMode.MANUAL:
            return RecommendationType.REQUIRE_APPROVAL, "Manual mode requires steward approval for every change."
        if candidate.sensitivity in {SensitivityClass.PHI, SensitivityClass.PII, SensitivityClass.FINANCIAL, SensitivityClass.REGULATORY}:
            return RecommendationType.REQUIRE_APPROVAL, "Sensitive field requires approval."
        if candidate.changeType in {
            ChangeType.ADD_RELATIONSHIP,
            ChangeType.RENAME_ATTRIBUTE,
            ChangeType.CHANGE_DATA_TYPE,
            ChangeType.DEPRECATE_ATTRIBUTE,
        }:
            return RecommendationType.REQUIRE_APPROVAL, "Change type is governed and requires approval."
        if candidate.confidenceScore < 0.75:
            return RecommendationType.REQUIRE_APPROVAL, "Low confidence recommendation requires review."
        if candidate.businessDomain in {DomainClass.CLAIM, DomainClass.DIAGNOSIS, DomainClass.MEDICATION}:
            return RecommendationType.REQUIRE_APPROVAL, "Clinical/claim domain requires review by policy."
        if governance_mode == GovernanceMode.ASSISTED:
            return RecommendationType.REQUIRE_APPROVAL, "Assisted mode requires approval before promotion."
        if governance_mode == GovernanceMode.CONTROLLED_AUTO_APPLY and candidate.confidenceScore >= 0.85 and candidate.riskLevel == RiskLevel.LOW:
            return RecommendationType.AUTO_APPLY, "Low-risk additive candidate met auto-apply threshold."
        return RecommendationType.REQUIRE_APPROVAL, "Default governance policy requires approval."

    def _build_fallback_recommendation(
        self,
        field: Dict[str, Any],
        ontology_attributes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        field_name = str(field.get("name") or "").strip()
        normalized = self._normalize_name(field_name)
        inferred_type = self._infer_type(field)
        best_match, sim = self._find_best_match(field_name, ontology_attributes)
        domain = self._detect_domain(normalized)
        sensitivity = self._detect_sensitivity(normalized)

        change_type = ChangeType.ADD_ATTRIBUTE
        suggested_entity = "GenericEntity"
        suggested_attribute = field_name
        rationale = [f"Field '{field_name}' normalized to '{normalized}' with inferred type '{inferred_type}'."]

        if best_match and sim > 0.9:
            change_type = ChangeType.DUPLICATE_OR_SYNONYM
            suggested_entity = str(best_match.get("class_name") or best_match.get("entity") or "ExistingEntity")
            suggested_attribute = str(best_match.get("name") or best_match.get("attribute_name") or field_name)
            rationale.append(f"High similarity ({sim:.2f}) to existing attribute '{suggested_attribute}'.")
        elif best_match and sim > 0.7:
            change_type = ChangeType.RENAME_ATTRIBUTE
            suggested_entity = str(best_match.get("class_name") or best_match.get("entity") or "ExistingEntity")
            rationale.append(f"Potential rename/synonym with similarity {sim:.2f}.")
        elif domain != DomainClass.GENERIC and any(x in normalized for x in ["id", "name", "score", "tier", "cluster"]):
            change_type = ChangeType.ADD_ATTRIBUTE
            suggested_entity = domain.value.capitalize()
            rationale.append(f"Domain keyword indicates entity placement under {suggested_entity}.")
        elif any(x in normalized for x in ["to_", "_to_", "_id_ref", "parent_"]):
            change_type = ChangeType.ADD_RELATIONSHIP
            rationale.append("Field pattern indicates possible relationship.")

        if sensitivity != SensitivityClass.NON_SENSITIVE:
            classification = [ChangeType.SENSITIVE_FIELD.value, ChangeType.POLICY_REVIEW_REQUIRED.value]
            risk = RiskLevel.HIGH
        else:
            classification = [change_type.value]
            risk = RiskLevel.LOW if sim >= 0.85 and change_type == ChangeType.ADD_ATTRIBUTE else RiskLevel.MEDIUM

        confidence = min(0.98, max(0.55, 0.55 + (sim * 0.4)))
        return {
            "changeType": change_type,
            "suggestedEntity": suggested_entity,
            "suggestedAttribute": suggested_attribute,
            "classification": classification,
            "businessDomain": domain,
            "sensitivity": sensitivity,
            "riskLevel": risk,
            "confidenceScore": confidence,
            "aiRationale": " ".join(rationale),
            "currentOntologyMatch": (best_match or {}).get("name") if best_match else None,
            "lineage": {
                "source_field": field_name,
                "normalized_field": normalized,
                "inferred_type": inferred_type,
                "similarity_score": round(sim, 4),
            },
        }

    def _build_llm_recommendation(self, field: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        provider = llm_router.ontology_provider()
        if not llm_router.is_provider_ready(provider):
            return fallback
        try:
            prompt = (
                "You are an ontology governance assistant. Return strict JSON with keys "
                "changeType,suggestedEntity,suggestedAttribute,classification,businessDomain,"
                "sensitivity,riskLevel,confidenceScore,aiRationale. "
                f"Input field: {field} fallback: {fallback}"
            )
            model = None
            if provider == "openai":
                model = "gpt-3.5-turbo"
            elif provider == "bedrock" and settings.BEDROCK_ONTOLOGY_MODEL_ID:
                model = settings.BEDROCK_ONTOLOGY_MODEL_ID

            content = llm_router.chat_completion(
                provider=provider,
                messages=[
                    {"role": "system", "content": "Return only JSON, no markdown."},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                temperature=0.1,
                max_tokens=350,
            )
            parsed = json.loads(content)
            parsed.setdefault("lineage", fallback["lineage"])
            parsed.setdefault("currentOntologyMatch", fallback["currentOntologyMatch"])
            return parsed
        except Exception:
            return fallback

    def _build_drift_fields(self, source_dataset_id: str, fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate synthetic fields that represent schema drift events."""
        previous = self.persistence.get_dataset_schema(source_dataset_id)
        prev_fields = previous.get("fields", []) if previous else []
        if not prev_fields:
            return []

        current_map = {self._normalize_name(str(f.get("name") or "")): f for f in fields if f.get("name")}
        previous_map = {self._normalize_name(str(f.get("name") or "")): f for f in prev_fields if f.get("name")}
        synthetic: List[Dict[str, Any]] = []

        # Type changes on existing fields.
        for norm, old_f in previous_map.items():
            if norm in current_map:
                old_t = self._infer_type(old_f)
                new_t = self._infer_type(current_map[norm])
                if old_t != new_t:
                    synthetic.append(
                        {
                            "name": str(current_map[norm].get("name")),
                            "type": new_t,
                            "sample_values": current_map[norm].get("sample_values", []),
                            "_forced_change_type": ChangeType.CHANGE_DATA_TYPE.value,
                            "_lineage_hint": {
                                "previous_type": old_t,
                                "new_type": new_t,
                                "previous_field_name": old_f.get("name"),
                            },
                        }
                    )

        removed_norms = {k for k in previous_map if k not in current_map}
        added_norms = {k for k in current_map if k not in previous_map}

        # Rename detection between removed and added fields by name similarity.
        renamed_removed: set[str] = set()
        renamed_added: set[str] = set()
        for r in removed_norms:
            for a in added_norms:
                sim = self._similarity(str(previous_map[r].get("name")), str(current_map[a].get("name")))
                if sim >= 0.88:
                    renamed_removed.add(r)
                    renamed_added.add(a)
                    synthetic.append(
                        {
                            "name": str(current_map[a].get("name")),
                            "type": self._infer_type(current_map[a]),
                            "sample_values": current_map[a].get("sample_values", []),
                            "_forced_change_type": ChangeType.RENAME_ATTRIBUTE.value,
                            "_lineage_hint": {
                                "renamed_from": previous_map[r].get("name"),
                                "renamed_to": current_map[a].get("name"),
                                "similarity_score": round(sim, 4),
                            },
                        }
                    )

        # Deprecation detection for truly removed fields.
        for r in removed_norms - renamed_removed:
            synthetic.append(
                {
                    "name": str(previous_map[r].get("name")),
                    "type": self._infer_type(previous_map[r]),
                    "sample_values": previous_map[r].get("sample_values", []),
                    "_forced_change_type": ChangeType.DEPRECATE_ATTRIBUTE.value,
                    "_lineage_hint": {
                        "removed_field_name": previous_map[r].get("name"),
                        "reason": "Field was present in previous schema and is missing in current schema.",
                    },
                }
            )

        return synthetic

    def discover_candidates(self, source_dataset_id: str, fields: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, created_by: str = "system") -> List[OntologyChangeCandidate]:
        metadata = metadata or {}
        governance_mode = self.persistence.get_governance_mode()
        baseline = self.persistence.get_current_ontology_snapshot()
        ontology_attributes = baseline.get("attributes", [])
        candidates: List[OntologyChangeCandidate] = []
        drift_fields = self._build_drift_fields(source_dataset_id, fields)
        all_fields = list(fields) + drift_fields

        for field in all_fields:
            fallback = self._build_fallback_recommendation(field, ontology_attributes)
            suggested = self._build_llm_recommendation(field, fallback)
            forced_change_type = field.get("_forced_change_type")
            if forced_change_type:
                suggested["changeType"] = forced_change_type

            candidate = OntologyChangeCandidate(
                id=f"chg_{uuid.uuid4().hex[:14]}",
                sourceDatasetId=source_dataset_id,
                changeType=ChangeType(suggested.get("changeType", fallback["changeType"])),
                suggestedEntity=suggested.get("suggestedEntity", fallback["suggestedEntity"]),
                suggestedAttribute=suggested.get("suggestedAttribute", fallback["suggestedAttribute"]),
                suggestedRelationship=suggested.get("suggestedRelationship"),
                currentOntologyMatch=suggested.get("currentOntologyMatch", fallback["currentOntologyMatch"]),
                classification=suggested.get("classification", fallback["classification"]),
                businessDomain=DomainClass(suggested.get("businessDomain", fallback["businessDomain"])),
                sensitivity=SensitivityClass(suggested.get("sensitivity", fallback["sensitivity"])),
                riskLevel=RiskLevel(suggested.get("riskLevel", fallback["riskLevel"])),
                confidenceScore=float(suggested.get("confidenceScore", fallback["confidenceScore"])),
                aiRationale=str(suggested.get("aiRationale", fallback["aiRationale"])),
                createdBy=created_by,
                lineage={
                    **fallback["lineage"],
                    "source_dataset": source_dataset_id,
                    "metadata": metadata,
                    **(field.get("_lineage_hint") or {}),
                },
                evidence={
                    "sample_values": field.get("sample_values", []),
                    "declared_type": field.get("type"),
                },
                createdAt=datetime.utcnow(),
                updatedAt=datetime.utcnow(),
            )
            decision, reason = self._policy_decision(candidate, governance_mode)
            candidate.policyDecision = decision
            candidate.recommendation = decision
            candidate.status = ChangeStatus.AUTO_APPLIED if decision == RecommendationType.AUTO_APPLY else ChangeStatus.PENDING_APPROVAL
            candidates.append(candidate)
            self.persistence.save_policy_decision(
                candidate.id,
                policy_rule="default_governance_policy",
                decision=decision,
                reason=reason,
            )

        self.persistence.save_candidates(candidates)
        self.persistence.save_dataset_schema(source_dataset_id, fields, metadata)
        self.persistence.save_audit_log(
            user=created_by,
            action="enrichment_discovery_run",
            before_state={},
            after_state={
                "source_dataset_id": source_dataset_id,
                "candidate_count": len(candidates),
                "drift_candidate_count": len(drift_fields),
            },
            rationale="Automated enrichment discovery executed.",
        )
        return candidates
