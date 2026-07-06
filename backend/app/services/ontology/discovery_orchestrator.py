"""Orchestrate the full ontology discovery pipeline (artifact -> version)."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional  # noqa: F401

from app.core.config import settings
from app.models.ontology import (
    OntologyVersion,
    DiscoveryRunStatus,
    DiscoveryRunStage,
    OntologyEvidence,
)

from .artifact_loader import ArtifactLoader
from .pdf_processor import PDFProcessor
from .docx_processor import DocxProcessor
from .xml_processor import XMLProcessor
from .image_processor import ImageProcessor
from .semantic_chunker import SemanticChunker
from .concept_extractor import ConceptExtractor
from .ontology_classifier import OntologyClassifier
from .relation_inference_engine import RelationInferenceEngine
from .attribute_mapper import AttributeMapper
from .ontology_assembler import OntologyAssembler
from .ontology_validator import OntologyValidator
from .ontology_persistence_service import OntologyPersistenceService
from .llm_ontology_service import LLMOntologyService

logger = logging.getLogger(__name__)


class DiscoveryOrchestrator:
    """Runs the full pipeline and updates run status."""

    def __init__(self):
        self.artifact_loader = ArtifactLoader()
        self.pdf_processor = PDFProcessor()
        self.docx_processor = DocxProcessor()
        self.xml_processor = XMLProcessor()
        self.image_processor = ImageProcessor()
        self.semantic_chunker = SemanticChunker(max_chunk_size=2000, overlap=200)
        self.concept_extractor = ConceptExtractor()
        self.ontology_classifier = OntologyClassifier()
        self.relation_engine = RelationInferenceEngine()
        self.attribute_mapper = AttributeMapper()
        self.assembler = OntologyAssembler()
        self.validator = OntologyValidator()
        self.persistence = OntologyPersistenceService()
        self.llm_service = LLMOntologyService()

    def run_discovery(
        self,
        run_id: str,
        project_id: str,
        artifact_ids: List[str],
        use_llm: bool = True,
        max_artifacts_per_run: Optional[int] = None,
        max_chunks_for_llm: Optional[int] = None,
    ) -> Optional[str]:
        """
        Execute pipeline; persist version and update run. Returns version_id on success.
        """
        def log(stage: str, msg: str, percent: float) -> None:
            self.persistence.update_run(
                run_id,
                current_stage=stage,
                progress_percent=percent,
                log_entry={"stage": stage, "message": msg},
            )

        self.persistence.update_run(run_id, status=DiscoveryRunStatus.RUNNING, started_at=datetime.utcnow())
        log(DiscoveryRunStage.ARTIFACT_LOAD.value, "Loading artifacts", 5.0)

        artifacts = self.artifact_loader.resolve_artifact_ids_to_paths(artifact_ids, project_id)
        if not artifacts:
            self.persistence.update_run(
                run_id,
                status=DiscoveryRunStatus.FAILED,
                error_message="No valid PDF/DOCX/XML artifacts found",
                completed_at=datetime.utcnow(),
            )
            return None

        max_artifacts = max_artifacts_per_run if max_artifacts_per_run is not None else (getattr(settings, "ONTOLOGY_MAX_ARTIFACTS_PER_RUN", 0) or 0)
        if max_artifacts > 0 and len(artifacts) > max_artifacts:
            log(DiscoveryRunStage.ARTIFACT_LOAD.value, f"Limiting to first {max_artifacts} of {len(artifacts)} artifacts", 6.0)
            artifacts = artifacts[:max_artifacts]

        all_text_chunks: List[Dict[str, Any]] = []
        all_evidence: List[OntologyEvidence] = []
        rule_entities: List[Dict[str, Any]] = []
        rule_relationships: List[Dict[str, Any]] = []
        rule_attributes: List[Dict[str, Any]] = []
        rule_rules: List[Dict[str, Any]] = []
        xml_hierarchy: List[Dict[str, Any]] = []
        xml_repeated: List[str] = []

        for art in artifacts:
            if art.source_type == "pdf":
                log(DiscoveryRunStage.PDF_PROCESS.value, f"Processing PDF {art.file_name}", 15.0)
                full_text, sections, ev_list = self.pdf_processor.process(art)
                all_evidence.extend(ev_list)
                chunks = self.semantic_chunker.chunk_sections(sections)
                for c in chunks:
                    c["artifact_id"] = art.id
                    c["artifact_type"] = "pdf"
                all_text_chunks.extend(chunks)
                for sec in sections:
                    extracted = self.concept_extractor.extract_from_text(
                        sec.get("content", ""),
                        evidence_list=ev_list,
                        source_artifact_id=art.id,
                        page_number=sec.get("page_number"),
                    )
                    rule_entities.extend(extracted["entities"])
                    rule_relationships.extend(extracted["relationships"])
                    rule_attributes.extend(extracted["attributes"])
                    rule_rules.extend(extracted["business_rules"])
            elif art.source_type == "docx":
                log(DiscoveryRunStage.PDF_PROCESS.value, f"Processing DOCX {art.file_name}", 18.0)
                full_text, sections, ev_list = self.docx_processor.process(art)
                all_evidence.extend(ev_list)
                chunks = self.semantic_chunker.chunk_sections(sections)
                for c in chunks:
                    c["artifact_id"] = art.id
                    c["artifact_type"] = "docx"
                all_text_chunks.extend(chunks)
                for sec in sections:
                    extracted = self.concept_extractor.extract_from_text(
                        sec.get("content", ""),
                        evidence_list=ev_list,
                        source_artifact_id=art.id,
                        page_number=sec.get("page_number"),
                    )
                    rule_entities.extend(extracted["entities"])
                    rule_relationships.extend(extracted["relationships"])
                    rule_attributes.extend(extracted["attributes"])
                    rule_rules.extend(extracted["business_rules"])
            elif art.source_type == "image":
                log(DiscoveryRunStage.PDF_PROCESS.value, f"Processing image {art.file_name}", 18.0)
                full_text, sections, ev_list = self.image_processor.process(art)
                all_evidence.extend(ev_list)
                chunks = self.semantic_chunker.chunk_sections(sections)
                for c in chunks:
                    c["artifact_id"] = art.id
                    c["artifact_type"] = "image"
                all_text_chunks.extend(chunks)
                for sec in sections:
                    extracted = self.concept_extractor.extract_from_text(
                        sec.get("content", ""),
                        evidence_list=ev_list,
                        source_artifact_id=art.id,
                        page_number=sec.get("page_number"),
                    )
                    rule_entities.extend(extracted["entities"])
                    rule_relationships.extend(extracted["relationships"])
                    rule_attributes.extend(extracted["attributes"])
                    rule_rules.extend(extracted["business_rules"])
            else:
                log(DiscoveryRunStage.XML_PROCESS.value, f"Processing XML {art.file_name}", 20.0)
                full_text, hierarchy, repeated, ev_list = self.xml_processor.process(art)
                all_evidence.extend(ev_list)
                xml_hierarchy.extend(hierarchy)
                xml_repeated.extend(repeated)
                chunks = self.semantic_chunker.chunk_text(full_text)
                for c in chunks:
                    c["artifact_id"] = art.id
                    c["artifact_type"] = "xml"
                all_text_chunks.extend(chunks)
                extracted = self.concept_extractor.extract_from_xml_hierarchy(
                    hierarchy, repeated, ev_list
                )
                rule_entities.extend(extracted["entities"])
                rule_attributes.extend(extracted["attributes"])

        # Tabular / fabric vector rows: "col: val | col: val" — verb-based rules miss these
        tabular_rb = self.concept_extractor.extract_from_tabular_row_chunks(all_text_chunks)
        rule_entities.extend(tabular_rb["entities"])
        rule_relationships.extend(tabular_rb["relationships"])
        rule_attributes.extend(tabular_rb["attributes"])

        max_chunks_total = getattr(settings, "ONTOLOGY_MAX_CHUNKS_TOTAL", 0) or 0
        if max_chunks_total > 0 and len(all_text_chunks) > max_chunks_total:
            log(DiscoveryRunStage.CONCEPT_EXTRACT.value, f"Using first {max_chunks_total} of {len(all_text_chunks)} chunks", 42.0)
            all_text_chunks = all_text_chunks[:max_chunks_total]

        log(DiscoveryRunStage.CONCEPT_EXTRACT.value, "Merging and classifying", 40.0)
        llm_candidates: Dict[str, List[Dict[str, Any]]] = {
            "entities": [], "relationships": [], "attributes": [], "business_rules": [],
        }
        max_llm_chunks = max_chunks_for_llm if max_chunks_for_llm is not None else (getattr(settings, "ONTOLOGY_MAX_CHUNKS_FOR_LLM", 10) or 10)
        if use_llm and self.llm_service.is_available():
            for i, chunk in enumerate(all_text_chunks[:max_llm_chunks]):
                result = self.llm_service.extract_from_chunk(chunk.get("content", ""))
                if result:
                    llm_candidates["entities"].extend(result.get("entities", []))
                    llm_candidates["relationships"].extend(result.get("relationships", []))
                    llm_candidates["attributes"].extend(result.get("attributes", []))
                    llm_candidates["business_rules"].extend(result.get("business_rules", []))

        rule_based = {
            "entities": rule_entities,
            "relationships": rule_relationships,
            "attributes": rule_attributes,
            "business_rules": rule_rules,
            "enumerations": [],
        }
        classified = self.ontology_classifier.classify_candidates(rule_based, llm_candidates)

        log(DiscoveryRunStage.RELATION_INFERENCE.value, "Inferring relationships", 55.0)
        entity_list = classified["entities"]
        tabular_rel_cands = [r for r in classified["relationships"] if r.get("tabular_binding")]
        normal_rel_cands = [r for r in classified["relationships"] if not r.get("tabular_binding")]
        rel_list = self.relation_engine.infer_relationships(
            entity_list,
            normal_rel_cands,
            all_text_chunks,
        )
        rel_list.extend(
            self.relation_engine.bind_tabular_relationship_candidates(
                entity_list, tabular_rel_cands
            )
        )

        log(DiscoveryRunStage.ATTRIBUTE_MAP.value, "Mapping attributes", 65.0)
        attr_list = self.attribute_mapper.map_attributes_to_classes(
            classified["attributes"],
            entity_list,
            xml_hierarchy if xml_hierarchy else None,
        )

        log(DiscoveryRunStage.ONTOLOGY_ASSEMBLE.value, "Assembling ontology", 75.0)
        assembled = self.assembler.assemble(
            project_id=project_id,
            version_label="draft",
            entities=entity_list,
            relationships=rel_list,
            attributes=attr_list,
            business_rules=classified["business_rules"],
            evidence_pool=all_evidence,
        )

        log(DiscoveryRunStage.ONTOLOGY_VALIDATE.value, "Validating", 85.0)
        is_valid, messages, stats = self.validator.validate(
            assembled["classes"], assembled["relationships"], assembled["attributes"]
        )
        if messages:
            log(DiscoveryRunStage.ONTOLOGY_VALIDATE.value, "; ".join(messages[:3]), 87.0)

        from app.models.ontology import OntologyClass, OntologyRelationship, OntologyAttribute, OntologyConstraint
        def to_class(c: Any): return OntologyClass(**c) if isinstance(c, dict) else c
        def to_rel(r: Any): return OntologyRelationship(**r) if isinstance(r, dict) else r
        def to_attr(a: Any): return OntologyAttribute(**a) if isinstance(a, dict) else a
        def to_con(c: Any): return OntologyConstraint(**c) if isinstance(c, dict) else c

        version = OntologyVersion(
            id=f"ver_{run_id.replace('run_', '')}",
            project_id=project_id,
            version_label="draft",
            is_draft=True,
            classes=[to_class(c) for c in assembled["classes"]],
            relationships=[to_rel(r) for r in assembled["relationships"]],
            attributes=[to_attr(a) for a in assembled["attributes"]],
            constraints=[to_con(c) for c in assembled["constraints"]],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        log(DiscoveryRunStage.PERSIST.value, "Saving version", 95.0)
        self.persistence.save_version(version)
        self.persistence.update_run(
            run_id,
            status=DiscoveryRunStatus.COMPLETED,
            progress_percent=100.0,
            result_version_id=version.id,
            completed_at=datetime.utcnow(),
            log_entry={"stage": "persist", "message": f"Version {version.id} saved", "stats": stats},
        )
        return version.id

    def run_schema_discovery(
        self,
        run_id: str,
        project_id: str,
        schema_profile: Dict[str, Any],
    ) -> Optional[str]:
        """Schema-first discovery for tabular/database fabrics (Phase 2 Layer 1)."""
        from app.services.ontology.schema_analyzer import schema_analyzer
        from app.services.ontology.ontology_db_repository import ontology_db_repository
        from app.models.ontology import OntologyClass, OntologyRelationship, OntologyAttribute, OntologyConstraint

        def log(stage: str, msg: str, percent: float) -> None:
            self.persistence.update_run(
                run_id,
                current_stage=stage,
                progress_percent=percent,
                log_entry={"stage": stage, "message": msg},
            )

        self.persistence.update_run(run_id, status=DiscoveryRunStatus.RUNNING, started_at=datetime.utcnow())
        log(DiscoveryRunStage.ARTIFACT_LOAD.value, "Analyzing schema profile", 10.0)

        analyzed = schema_analyzer.analyze(schema_profile)
        entities = analyzed.get("entities") or []
        rel_candidates = []
        for r in analyzed.get("relationships") or []:
            rel_candidates.append({
                **r,
                "relationship_name": r.get("name") or "references",
                "source_entity_normalized": r.get("source_entity") or r.get("source"),
                "target_entity_normalized": r.get("target_entity") or r.get("target"),
                "tabular_binding": True,
            })

        log(DiscoveryRunStage.RELATION_INFERENCE.value, "Binding tabular relationships", 50.0)
        rel_list = self.relation_engine.bind_tabular_relationship_candidates(entities, rel_candidates)

        attrs = []
        entity_by_norm = {e.get("normalized_name"): e.get("id") for e in entities}
        for a in analyzed.get("attributes") or []:
            class_id = entity_by_norm.get(a.get("entity"))
            if not class_id:
                continue
            attrs.append({
                **a,
                "class_id": class_id,
                "attribute_name": a.get("name"),
            })

        log(DiscoveryRunStage.ONTOLOGY_ASSEMBLE.value, "Assembling ontology", 75.0)
        assembled = self.assembler.assemble(
            project_id=project_id,
            version_label="draft",
            entities=entities,
            relationships=rel_list,
            attributes=attrs,
            business_rules=[],
            evidence_pool=[],
        )

        log(DiscoveryRunStage.ONTOLOGY_VALIDATE.value, "Validating", 85.0)
        is_valid, messages, stats = self.validator.validate(
            assembled["classes"], assembled["relationships"], assembled["attributes"]
        )

        version = OntologyVersion(
            id=f"ver_{run_id.replace('run_', '')}",
            project_id=project_id,
            version_label="draft",
            is_draft=True,
            classes=[OntologyClass(**c) if isinstance(c, dict) else c for c in assembled["classes"]],
            relationships=[OntologyRelationship(**r) if isinstance(r, dict) else r for r in assembled["relationships"]],
            attributes=[OntologyAttribute(**a) if isinstance(a, dict) else a for a in assembled["attributes"]],
            constraints=[OntologyConstraint(**c) if isinstance(c, dict) else c for c in assembled["constraints"]],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        log(DiscoveryRunStage.PERSIST.value, "Saving version", 95.0)
        ontology_db_repository.save_version(version)
        self.persistence.update_run(
            run_id,
            status=DiscoveryRunStatus.COMPLETED,
            progress_percent=100.0,
            result_version_id=version.id,
            completed_at=datetime.utcnow(),
            log_entry={"stage": "persist", "message": f"Version {version.id} saved", "stats": stats},
        )
        return version.id
