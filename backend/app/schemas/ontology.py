"""Ontology API request/response schemas (DTOs)."""
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.ontology import (
    OntologyClass,
    OntologyRelationship,
    OntologyAttribute,
    OntologyConstraint,
    OntologyEvidence,
    OntologyVersion,
    OntologyProject,
    SourceArtifact,
    DiscoveryRun,
    DiscoveryRunStatus,
    GovernanceMode,
)


# --- Request DTOs ---


class DiscoverOntologyRequest(BaseModel):
    """Request to start ontology discovery for a project."""
    project_id: Optional[str] = None  # optional when provided in path
    artifact_ids: List[str] = Field(..., description="File names or paths to process (PDF/XML/images)")
    use_llm: bool = True
    llm_provider: Optional[str] = "openai"
    max_artifacts_per_run: Optional[int] = Field(None, description="Cap artifacts per run for large catalogs (uses config if unset)")
    max_chunks_for_llm: Optional[int] = Field(None, description="Cap chunks sent to LLM per run (uses config if unset)")


class OntologyClassUpdate(BaseModel):
    """Update payload for an ontology class."""
    name: Optional[str] = None
    normalized_name: Optional[str] = None
    definition: Optional[str] = None
    aliases: Optional[List[str]] = None
    status: Optional[str] = None


class OntologyRelationshipUpdate(BaseModel):
    """Update payload for an ontology relationship."""
    relationship_name: Optional[str] = None
    definition: Optional[str] = None
    cardinality_if_detected: Optional[str] = None
    status: Optional[str] = None


class OntologyAttributeUpdate(BaseModel):
    """Update payload for an ontology attribute."""
    attribute_name: Optional[str] = None
    normalized_name: Optional[str] = None
    data_type_guess: Optional[str] = None
    required_flag_guess: Optional[bool] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ReviewApproveRequest(BaseModel):
    """Approve one or more ontology elements."""
    version_id: str
    element_type: str  # class | relationship | attribute | constraint
    element_ids: List[str]


class ReviewRejectRequest(BaseModel):
    """Reject one or more ontology elements."""
    version_id: str
    element_type: str
    element_ids: List[str]
    reason: Optional[str] = None


class MergeRequest(BaseModel):
    """Merge duplicate entities."""
    version_id: str
    source_class_ids: List[str]
    target_class_id: str
    merge_attributes: bool = True
    merge_relationships: bool = True


class CreateProjectRequest(BaseModel):
    """Create a new ontology project."""
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None


class AddArtifactsRequest(BaseModel):
    """Associate artifacts (files) with a project."""
    project_id: str
    artifact_ids: List[str]  # file paths or names from upload repo
    version_tag: Optional[str] = None


class OntologyChatRequest(BaseModel):
    """Real-time query: user message and optional ontology context."""
    version_id: Optional[str] = None
    message: str
    context: Optional[Dict[str, Any]] = None  # selected_type, selected_name, selected_summary
    history: Optional[List[Dict[str, str]]] = None  # [{ role, content }]


class EnrichmentDiscoverRequest(BaseModel):
    source_dataset_id: str
    fields: List[Dict[str, Any]] = Field(default_factory=list, description="List of fields with name, type, and optional sample_values")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"


class CandidateReviewRequest(BaseModel):
    reviewer: str = "steward"
    notes: Optional[str] = None


class GovernanceModeUpdateRequest(BaseModel):
    mode: GovernanceMode
    updated_by: str = "admin"


class EnrichmentDiscoverFromProjectRequest(BaseModel):
    project_id: str
    version_id: Optional[str] = None
    created_by: str = "system"


class CreateProjectFromFabricRequest(BaseModel):
    fabric_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None


class AgentQueryRequest(BaseModel):
    """Execute an agent-focused query against a selected ontology version."""
    project_id: str
    version_id: str
    query: str
    top_k: int = 5
    role: str = "agent_developer"
    include_debug: bool = True


class AgentDataContractUpsertRequest(BaseModel):
    """Create or update a versioned agent data contract."""
    contract_id: str
    name: str
    version: str
    description: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    compatibility: str = "backward_compatible"
    owner: str = "platform"
    tags: List[str] = Field(default_factory=list)

    @classmethod
    def _is_semver(cls, value: str) -> bool:
        return bool(re.match(r"^\d+\.\d+\.\d+$", value or ""))

    @classmethod
    def _valid_compatibility(cls, value: str) -> bool:
        return value in {"backward_compatible", "forward_compatible", "breaking_change"}

    def model_post_init(self, __context: Any) -> None:
        if not self._is_semver(self.version):
            raise ValueError("version must follow semantic versioning (e.g. 1.0.0)")
        if not self._valid_compatibility(self.compatibility):
            raise ValueError("compatibility must be backward_compatible, forward_compatible, or breaking_change")


class AgentDataContractDeleteRequest(BaseModel):
    """Delete a saved agent data contract by id and semver version."""

    contract_id: str
    version: str


class AgentPolicyEvaluateRequest(BaseModel):
    """Evaluate policy and masking rules for a query result."""
    role: str
    purpose: Optional[str] = "general"
    payload: Dict[str, Any] = Field(default_factory=dict)
    strict_mode: bool = False


# --- Response DTOs ---


class DiscoverOntologyResponse(BaseModel):
    """Response after starting discovery."""
    success: bool
    run_id: str
    project_id: str
    status: str
    message: str


class RunStatusResponse(BaseModel):
    """Discovery run status."""
    run_id: str
    project_id: str
    status: DiscoveryRunStatus
    current_stage: Optional[str] = None
    progress_percent: float
    result_version_id: Optional[str] = None
    error_message: Optional[str] = None
    run_logs: List[Dict[str, Any]] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class OntologyExportFormat(str):
    JSON = "json"
    CSV = "csv"
    GRAPH = "graph"


# Re-export model types for API response models
# API responses use the same domain models; no extra DTO layer needed for reads.
