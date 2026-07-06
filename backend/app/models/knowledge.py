from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SourceType(str, Enum):
    PDF = "pdf"
    DATABASE = "database"
    TEXT = "text"
    MIXED = "mixed"

class UploadRequest(BaseModel):
    source_type: SourceType
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class DatabaseConnection(BaseModel):
    host: str
    port: int
    database: str
    username: str
    password: str
    table_name: str
    query: Optional[str] = None
    # MongoDB Atlas specific fields
    connection_string: Optional[str] = None
    collection_name: Optional[str] = None
    database_type: str = "postgresql"  # postgresql, mysql, sqlite, mongodb

class MongoDBConnection(BaseModel):
    connection_string: str
    database_name: str
    collection_name: str
    query: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 1000
    projection: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    filters: Optional[Dict[str, Any]] = None

class KnowledgeSource(BaseModel):
    id: str
    name: str
    source_type: SourceType
    description: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    document_count: int
    status: str

class SearchResult(BaseModel):
    id: str
    content: str
    source: str
    similarity_score: float
    metadata: Dict[str, Any] = {}
    page_number: Optional[int] = None

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_results: int
    query: str
    processing_time: float

class TrainingRequest(BaseModel):
    model_name: Optional[str] = None
    epochs: int = Field(default=3, ge=1, le=10)
    learning_rate: float = Field(default=2e-5, ge=1e-6, le=1e-3)
    batch_size: int = Field(default=32, ge=8, le=128)

class TrainingResponse(BaseModel):
    model_id: str
    status: str
    progress: float
    message: str

class FabricGuardrails(BaseModel):
    data_classification: Optional[str] = "internal"
    compliance_tags: List[str] = Field(default_factory=list)
    pii_fields: List[str] = Field(default_factory=list)
    enforce_masking: bool = True
    encryption_at_rest: bool = True
    encryption_in_transit: bool = True
    row_level_security: bool = False
    approved_roles: List[str] = Field(default_factory=list)
    handbook_files: List[str] = Field(default_factory=list)

class CreatePDFFabricRequest(BaseModel):
    files: List[str]
    source_type: str = "pdf"
    train_model: bool = True
    """weave_domain: generic (default) or pharma — tags fabric for Weave journey (graph, ontology)."""
    weave_domain: Optional[str] = None
    """Optional profile e.g. scientific_documents, lims_table — stored for UI provenance."""
    connector_profile: Optional[str] = None
    guardrails: Optional[FabricGuardrails] = None

class CreateCompositeFabricRequest(BaseModel):
    name: str
    source_ids: List[str]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    guardrails: Optional[FabricGuardrails] = None

class KnowledgeStats(BaseModel):
    total_sources: int
    total_documents: int
    total_embeddings: int
    model_status: str
    last_training: Optional[datetime] = None

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None 