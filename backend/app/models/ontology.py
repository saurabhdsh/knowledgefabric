"""
Ontology Discovery domain models.
Domain-agnostic structures for entities, relationships, attributes, constraints, and evidence.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class OntologyElementStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class OntologyConstraintType(str, Enum):
    REQUIRED = "required"
    UNIQUE = "unique"
    RANGE = "range"
    PATTERN = "pattern"
    REFERENCE = "reference"
    BUSINESS_RULE = "business_rule"
    CARDINALITY = "cardinality"


class ExtractionSourceType(str, Enum):
    RULE_BASED = "rule_based"
    LLM = "llm"
    COMBINED = "combined"


# --- Evidence & traceability ---


class OntologyEvidence(BaseModel):
    """Traceability from ontology element back to source artifact."""
    id: str
    artifact_id: str
    artifact_type: str  # pdf | xml
    page_number: Optional[int] = None
    xml_path: Optional[str] = None
    text_snippet: str
    extraction_stage: str
    created_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "evt_1",
                "artifact_id": "art_1",
                "artifact_type": "pdf",
                "page_number": 3,
                "text_snippet": "Claim must have a valid policy number.",
                "extraction_stage": "concept_extractor"
            }
        }


# --- Core ontology elements ---


class OntologyClass(BaseModel):
    """Entity/class in the domain ontology."""
    id: str
    name: str
    normalized_name: str
    definition: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    source_evidence: List[OntologyEvidence] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    status: OntologyElementStatus = OntologyElementStatus.DRAFT
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    extraction_source: ExtractionSourceType = ExtractionSourceType.COMBINED

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cls_1",
                "name": "Claim",
                "normalized_name": "Claim",
                "definition": "A request for payment under an insurance policy.",
                "confidence_score": 0.92,
                "status": "draft"
            }
        }


class OntologyRelationship(BaseModel):
    """Relationship between two classes."""
    id: str
    source_class_id: str
    relationship_name: str
    target_class_id: str
    definition: Optional[str] = None
    evidence: List[OntologyEvidence] = Field(default_factory=list)
    cardinality_if_detected: Optional[str] = None  # e.g. "1:1", "1:n", "n:m"
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    status: OntologyElementStatus = OntologyElementStatus.DRAFT
    extraction_source: ExtractionSourceType = ExtractionSourceType.COMBINED
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OntologyAttribute(BaseModel):
    """Attribute belonging to a class."""
    id: str
    class_id: str
    attribute_name: str
    normalized_name: str
    data_type_guess: Optional[str] = None
    required_flag_guess: bool = False
    description: Optional[str] = None
    evidence: List[OntologyEvidence] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    status: OntologyElementStatus = OntologyElementStatus.DRAFT
    extraction_source: ExtractionSourceType = ExtractionSourceType.COMBINED
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OntologyConstraint(BaseModel):
    """Constraint or business rule."""
    id: str
    constraint_type: OntologyConstraintType
    expression: str
    related_class_id: Optional[str] = None
    related_attribute_id: Optional[str] = None
    evidence: List[OntologyEvidence] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    status: OntologyElementStatus = OntologyElementStatus.DRAFT
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OntologyMapping(BaseModel):
    """Mapping to external/canonical model (extensibility for FHIR/SNOMED/ACORD)."""
    id: str
    ontology_element_type: str  # class | relationship | attribute
    ontology_element_id: str
    external_system: str
    external_id: Optional[str] = None
    external_label: Optional[str] = None
    mapping_confidence: float = 0.0
    created_at: Optional[datetime] = None


class OntologyReviewDecision(BaseModel):
    """Human review decision on a candidate."""
    id: str
    element_type: str  # class | relationship | attribute | constraint
    element_id: str
    decision: str  # approve | reject | merge | convert_to_entity | convert_to_attribute
    reviewed_by: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    merged_into_id: Optional[str] = None


# --- Source artifacts ---


class SourceArtifact(BaseModel):
    """A PDF or XML file associated with an ontology project."""
    id: str
    file_name: str
    file_path: str
    source_type: str  # pdf | xml
    project_id: str
    ingestion_time: Optional[datetime] = None
    version: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --- Project & versioning ---


class OntologyVersion(BaseModel):
    """A versioned snapshot of the ontology (draft or approved)."""
    id: str
    project_id: str
    version_label: str  # e.g. "1.0", "draft"
    is_draft: bool = True
    classes: List[OntologyClass] = Field(default_factory=list)
    relationships: List[OntologyRelationship] = Field(default_factory=list)
    attributes: List[OntologyAttribute] = Field(default_factory=list)
    constraints: List[OntologyConstraint] = Field(default_factory=list)
    review_decisions: List[OntologyReviewDecision] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class OntologyProject(BaseModel):
    """Ontology workspace / project grouping artifacts and versions."""
    id: str
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None
    source_artifacts: List[SourceArtifact] = Field(default_factory=list)
    current_version_id: Optional[str] = None
    version_ids: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- Discovery run (async job) ---


class DiscoveryRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoveryRunStage(str, Enum):
    ARTIFACT_LOAD = "artifact_load"
    PDF_PROCESS = "pdf_process"
    XML_PROCESS = "xml_process"
    SEMANTIC_CHUNK = "semantic_chunk"
    CONCEPT_EXTRACT = "concept_extract"
    ONTOLOGY_CLASSIFY = "ontology_classify"
    RELATION_INFERENCE = "relation_inference"
    ATTRIBUTE_MAP = "attribute_map"
    ONTOLOGY_ASSEMBLE = "ontology_assemble"
    ONTOLOGY_VALIDATE = "ontology_validate"
    PERSIST = "persist"


class DiscoveryRun(BaseModel):
    """A single ontology discovery run (job)."""
    id: str
    project_id: str
    status: DiscoveryRunStatus = DiscoveryRunStatus.QUEUED
    current_stage: Optional[DiscoveryRunStage] = None
    progress_percent: float = 0.0
    artifact_ids: List[str] = Field(default_factory=list)
    result_version_id: Optional[str] = None
    error_message: Optional[str] = None
    run_logs: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# --- Enrichment and governance ---


class GovernanceMode(str, Enum):
    MANUAL = "manual"
    ASSISTED = "assisted"
    CONTROLLED_AUTO_APPLY = "controlled_auto_apply"


class OntologyEnvironment(str, Enum):
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"


class ChangeType(str, Enum):
    ADD_ATTRIBUTE = "add_attribute"
    ADD_ENTITY = "add_entity"
    ADD_RELATIONSHIP = "add_relationship"
    RENAME_ATTRIBUTE = "rename_attribute"
    CHANGE_DATA_TYPE = "change_data_type"
    DEPRECATE_ATTRIBUTE = "deprecate_attribute"
    DUPLICATE_OR_SYNONYM = "duplicate_or_synonym"
    SENSITIVE_FIELD = "sensitive_field"
    POLICY_REVIEW_REQUIRED = "policy_review_required"
    SAFE_AUTO_APPLY_CANDIDATE = "safe_auto_apply_candidate"


class ChangeStatus(str, Enum):
    DISCOVERED = "discovered"
    SUGGESTED = "suggested"
    CLASSIFIED = "classified"
    PENDING_APPROVAL = "pending_approval"
    AUTO_APPLIED = "auto_applied"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    PROMOTED = "promoted"
    SUPERSEDED = "superseded"


class RecommendationType(str, Enum):
    AUTO_APPLY = "auto_apply"
    REQUIRE_APPROVAL = "require_approval"
    REJECT = "reject"
    COMPLIANCE_REVIEW = "compliance_review"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DomainClass(str, Enum):
    MEMBER = "member"
    PROVIDER = "provider"
    CLAIM = "claim"
    POLICY = "policy"
    AUTHORIZATION = "authorization"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    CARE_MANAGEMENT = "care_management"
    FINANCE = "finance"
    GENERIC = "generic"


class SensitivityClass(str, Enum):
    NON_SENSITIVE = "non_sensitive"
    PII = "pii"
    PHI = "phi"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    UNKNOWN = "unknown"


class OntologyEntityRecord(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    domain: DomainClass = DomainClass.GENERIC
    version: int = 1
    status: str = "active"
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class OntologyAttributeRecord(BaseModel):
    id: str
    entityId: str
    name: str
    dataType: str = "string"
    description: Optional[str] = None
    sensitivity: SensitivityClass = SensitivityClass.UNKNOWN
    required: bool = False
    sourceMappings: List[Dict[str, Any]] = Field(default_factory=list)
    version: int = 1
    status: str = "active"


class OntologyRelationshipRecord(BaseModel):
    id: str
    sourceEntityId: str
    targetEntityId: str
    relationshipType: str
    description: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    version: int = 1
    status: str = "active"


class OntologyChangeCandidate(BaseModel):
    id: str
    sourceDatasetId: str
    changeType: ChangeType
    suggestedEntity: Optional[str] = None
    suggestedAttribute: Optional[str] = None
    suggestedRelationship: Optional[str] = None
    currentOntologyMatch: Optional[str] = None
    classification: List[str] = Field(default_factory=list)
    businessDomain: DomainClass = DomainClass.GENERIC
    sensitivity: SensitivityClass = SensitivityClass.UNKNOWN
    riskLevel: RiskLevel = RiskLevel.MEDIUM
    confidenceScore: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation: RecommendationType = RecommendationType.REQUIRE_APPROVAL
    aiRationale: str = ""
    policyDecision: Optional[RecommendationType] = None
    status: ChangeStatus = ChangeStatus.DISCOVERED
    createdBy: str = "system"
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[datetime] = None
    promotedVersion: Optional[str] = None
    lineage: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class OntologyVersionRecord(BaseModel):
    id: str
    versionNumber: str
    environment: OntologyEnvironment = OntologyEnvironment.DRAFT
    changeSummary: str
    changeIds: List[str] = Field(default_factory=list)
    approvedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    rollbackReference: Optional[str] = None
    status: str = "active"
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class PolicyDecisionLog(BaseModel):
    id: str
    candidateId: str
    policyRule: str
    decision: RecommendationType
    reason: str
    timestamp: Optional[datetime] = None


class OntologyAuditLog(BaseModel):
    id: str
    user: str
    timestamp: Optional[datetime] = None
    action: str
    beforeState: Dict[str, Any] = Field(default_factory=dict)
    afterState: Dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None
