"""Unit tests for ontology extraction pipeline."""
import os
import tempfile
import pytest
from app.models.ontology import SourceArtifact
from app.services.ontology import (
    PDFProcessor,
    XMLProcessor,
    SemanticChunker,
    ConceptExtractor,
    OntologyClassifier,
    RelationInferenceEngine,
    AttributeMapper,
    OntologyAssembler,
    OntologyValidator,
)


@pytest.fixture
def sample_xml_path():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "sample.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("""<?xml version="1.0"?>
<Root>
  <Claim>
    <claim_id>string</claim_id>
    <policy_number>string</policy_number>
  </Claim>
  <Policy>
    <policy_id>string</policy_id>
  </Policy>
</Root>""")
    yield path
    try:
        os.remove(path)
        os.rmdir(d)
    except Exception:
        pass


@pytest.fixture
def xml_artifact(sample_xml_path):
    return SourceArtifact(
        id="art_test_1",
        file_name="sample.xml",
        file_path=sample_xml_path,
        source_type="xml",
        project_id="proj_1",
    )


class TestXMLProcessor:
    def test_process_returns_text_and_hierarchy(self, xml_artifact):
        processor = XMLProcessor()
        full_text, hierarchy, repeated, evidence = processor.process(xml_artifact)
        assert isinstance(full_text, str)
        assert "string" in full_text or "Claim" in full_text
        assert len(hierarchy) >= 3
        assert any(n.get("tag") == "Claim" for n in hierarchy)
        assert any(n.get("is_leaf") for n in hierarchy)
        assert len(evidence) > 0


class TestSemanticChunker:
    def test_chunk_text(self):
        chunker = SemanticChunker(max_chunk_size=100, overlap=20)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 1
        assert all("content" in c and "index" in c for c in chunks)

    def test_chunk_sections(self):
        chunker = SemanticChunker(max_chunk_size=200, overlap=20)
        sections = [{"heading": "Section A", "content": "Some content here.", "page_number": 1}]
        chunks = chunker.chunk_sections(sections)
        assert len(chunks) >= 1
        assert chunks[0].get("heading") == "Section A"


class TestConceptExtractor:
    def test_extract_from_text(self):
        extractor = ConceptExtractor()
        text = "The Claim has a policy number. The Policy must be valid. Claimant Name is required."
        out = extractor.extract_from_text(text)
        assert "entities" in out
        assert "relationships" in out
        assert "attributes" in out
        assert "business_rules" in out
        assert len(out["entities"]) >= 1
        assert len(out["attributes"]) >= 1 or len(out["entities"]) >= 1

    def test_extract_from_xml_hierarchy(self):
        extractor = ConceptExtractor()
        hierarchy = [
            {"path": "Root/Claim", "tag": "Claim", "is_leaf": False, "text_sample": ""},
            {"path": "Root/Claim/claim_id", "tag": "claim_id", "is_leaf": True, "text_sample": "string"},
        ]
        repeated = ["Root/Claim"]
        evidence = []
        out = extractor.extract_from_xml_hierarchy(hierarchy, repeated, evidence)
        assert len(out["entities"]) >= 1
        assert len(out["attributes"]) >= 1


class TestOntologyClassifier:
    def test_classify_merge_and_dedupe(self):
        classifier = OntologyClassifier()
        rule_based = {
            "entities": [{"name": "Claim", "normalized_name": "Claim", "confidence": 0.7}],
            "relationships": [],
            "attributes": [{"name": "claim_id", "normalized_name": "Claim Id", "confidence": 0.8}],
            "business_rules": [],
            "enumerations": [],
        }
        llm = {
            "entities": [{"name": "Claim", "normalized_name": "Claim", "confidence": 0.9}],
            "relationships": [],
            "attributes": [],
            "business_rules": [],
        }
        out = classifier.classify_candidates(rule_based, llm)
        assert len(out["entities"]) >= 1
        assert len(out["attributes"]) >= 1


class TestRelationInferenceEngine:
    def test_infer_relationships(self):
        engine = RelationInferenceEngine()
        entities = [
            {"id": "e1", "name": "Claim", "normalized_name": "Claim"},
            {"id": "e2", "name": "Policy", "normalized_name": "Policy"},
        ]
        rel_candidates = [{"name": "has", "normalized_name": "has", "evidence_snippet": "Claim has Policy", "confidence": 0.6}]
        chunks = []
        rels = engine.infer_relationships(entities, rel_candidates, chunks)
        assert len(rels) >= 1
        assert rels[0].get("relationship_name") == "has"


class TestAttributeMapper:
    def test_map_attributes_to_classes(self):
        mapper = AttributeMapper()
        attributes = [
            {"id": "a1", "name": "claim_id", "normalized_name": "Claim Id", "xml_path": "Root/Claim/claim_id", "confidence": 0.8},
        ]
        entities = [{"id": "e1", "name": "Claim", "normalized_name": "Claim", "xml_path": "Root/Claim"}]
        hierarchy = [
            {"path": "Root/Claim", "parent_path": "Root", "is_leaf": False},
            {"path": "Root/Claim/claim_id", "parent_path": "Root/Claim", "is_leaf": True},
        ]
        result = mapper.map_attributes_to_classes(attributes, entities, hierarchy)
        assert len(result) == 1
        assert result[0]["class_id"] == "e1"


class TestOntologyAssembler:
    def test_assemble_produces_classes_rels_attrs(self):
        assembler = OntologyAssembler()
        entities = [{"id": "e1", "name": "Claim", "normalized_name": "Claim", "confidence": 0.8}]
        relationships = [{"id": "r1", "source_class_id": "e1", "relationship_name": "has", "target_class_id": "e2", "confidence": 0.5}]
        attributes = [{"id": "a1", "class_id": "e1", "attribute_name": "claim_id", "normalized_name": "Claim Id", "confidence": 0.7}]
        assembled = assembler.assemble(
            project_id="p1",
            version_label="draft",
            entities=entities,
            relationships=relationships,
            attributes=attributes,
            business_rules=[],
        )
        assert len(assembled["classes"]) == 1
        assert len(assembled["relationships"]) == 1
        assert len(assembled["attributes"]) == 1


class TestOntologyValidator:
    def test_validate_ok(self):
        validator = OntologyValidator()
        classes = [{"id": "c1"}, {"id": "c2"}]
        relationships = [{"id": "r1", "source_class_id": "c1", "target_class_id": "c2"}]
        attributes = [{"id": "a1", "class_id": "c1"}]
        valid, messages, stats = validator.validate(classes, relationships, attributes)
        assert valid is True
        assert stats["classes_count"] == 2

    def test_validate_fails_on_bad_ref(self):
        validator = OntologyValidator()
        classes = [{"id": "c1"}]
        relationships = [{"id": "r1", "source_class_id": "c1", "target_class_id": "c99"}]
        attributes = []
        valid, messages, stats = validator.validate(classes, relationships, attributes)
        assert valid is False
