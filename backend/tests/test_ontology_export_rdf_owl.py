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


def test_duplicate_relationship_names_do_not_share_one_rdf_property():
    """Two links with the same name must not overwrite each other's domain."""
    version = _sample_version()
    version.relationships.append(
        OntologyRelationship(
            id="rel_2",
            source_class_id="cls_member",
            relationship_name="references_members",
            target_class_id="cls_claim",
            cardinality_if_detected="1:n",
            confidence_score=0.7,
            status=OntologyElementStatus.DRAFT,
        )
    )
    version.classes[1].parent_class_id = "cls_member"  # claims under members — for the subclass test below
    ttl = OntologyExportService().export_rdf_turtle(version)
    assert ttl.count("weave:references_members a rdf:Property") == 1
    assert "weave:references_members_2 a rdf:Property" in ttl
    assert "rdfs:domain weave:claims" in ttl
    assert "rdfs:domain weave:members" in ttl
    assert "rdfs:subClassOf weave:members" in ttl


def test_export_shacl_emits_required_fields_and_cardinality():
    shacl = OntologyExportService().export_shacl(_sample_version())
    assert "@prefix sh:" in shacl
    assert "weave:membersShape a sh:NodeShape" in shacl
    assert "sh:targetClass weave:members" in shacl
    assert "sh:minCount 1" in shacl  # required member_id
    assert "sh:maxCount 1" in shacl  # n:1 relationship
    assert "sh:path weave:references_members" in shacl
