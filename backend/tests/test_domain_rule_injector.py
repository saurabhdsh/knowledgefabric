"""Domain-pack business rules → ontology constraints."""
from __future__ import annotations

from app.models.ontology import OntologyClass, OntologyElementStatus, OntologyVersion
from app.services.domain_packs import get_pack
from app.services.ontology.domain_rule_injector import inject_business_rules


def test_cost_of_care_pack_exposes_business_rules():
    pack = get_pack("healthcare_cost_of_care")
    assert pack is not None
    rules = pack.business_rules()
    assert len(rules) >= 8
    assert any("Avoidable ER" in r["expression"] for r in rules)


def test_inject_business_rules_links_related_classes():
    version = OntologyVersion(
        id="ver_rules_test",
        project_id="proj_rules_test",
        version_label="draft",
        is_draft=True,
        classes=[
            OntologyClass(
                id="cls_m",
                name="members",
                normalized_name="Members",
                confidence_score=0.9,
                status=OntologyElementStatus.DRAFT,
            ),
            OntologyClass(
                id="cls_c",
                name="claims",
                normalized_name="Claims",
                confidence_score=0.9,
                status=OntologyElementStatus.DRAFT,
            ),
        ],
    )
    out = inject_business_rules(version, persist=False)
    assert len(out.constraints) >= 8
    linked = [c for c in out.constraints if c.related_class_id in {"cls_m", "cls_c"}]
    assert linked
    # Idempotent
    out2 = inject_business_rules(out, persist=False)
    assert len(out2.constraints) == len(out.constraints)
