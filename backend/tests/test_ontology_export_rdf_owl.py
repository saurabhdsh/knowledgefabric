"""RDF Turtle + OWL export for ontology versions."""
from __future__ import annotations

from app.models.ontology import (
    OntologyAttribute,
    OntologyClass,
    OntologyElementStatus,
    OntologyRelationship,
    OntologyVersion,
)
from app.services.ontology.ontology_export_service import OntologyExportService


def _sample_version() -> OntologyVersion:
    member = OntologyClass(
        id="cls_member",
        name="members",
        normalized_name="members",
        definition="Plan member",
        confidence_score=0.9,
        status=OntologyElementStatus.DRAFT,
    )
    claim = OntologyClass(
        id="cls_claim",
        name="claims",
        normalized_name="claims",
        definition="Medical claim",
        confidence_score=0.88,
        status=OntologyElementStatus.DRAFT,
    )
    rel = OntologyRelationship(
        id="rel_1",
        source_class_id="cls_claim",
        relationship_name="references_members",
        target_class_id="cls_member",
        cardinality_if_detected="n:1",
        confidence_score=0.8,
        status=OntologyElementStatus.DRAFT,
    )
    attr = OntologyAttribute(
        id="attr_1",
        class_id="cls_member",
        attribute_name="member_id",
        normalized_name="member_id",
        data_type_guess="string",
        required_flag_guess=True,
        confidence_score=0.95,
        status=OntologyElementStatus.DRAFT,
    )
    return OntologyVersion(
        id="ver_test_export",
        project_id="proj_test_export",
        version_label="draft",
        is_draft=True,
        classes=[member, claim],
        relationships=[rel],
        attributes=[attr],
    )


def test_export_rdf_turtle_contains_classes_and_properties():
    svc = OntologyExportService()
    ttl = svc.export_rdf_turtle(_sample_version())
    assert "@prefix rdfs:" in ttl
    assert "weave:members a rdfs:Class" in ttl
    assert "weave:claims a rdfs:Class" in ttl
    assert "weave:references_members a rdf:Property" in ttl
    assert "rdfs:domain weave:claims" in ttl
    assert "rdfs:range weave:members" in ttl
    assert "member_id" in ttl
    assert "xsd:string" in ttl


def test_export_owl_contains_ontology_classes_and_object_properties():
    svc = OntologyExportService()
    owl = svc.export_owl(_sample_version())
    assert "@prefix owl:" in owl
    assert "a owl:Ontology" in owl
    assert "weave:members a owl:Class" in owl
    assert "weave:references_members a owl:ObjectProperty" in owl
    assert "owl:DatatypeProperty" in owl
    assert "weave:required" in owl
