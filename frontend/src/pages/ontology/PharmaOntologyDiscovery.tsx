import React, { useState } from 'react';

export type PharmaDiscoveryTab =
  | 'scientific_entities'
  | 'experiment_mapping'
  | 'batch_lineage'
  | 'process_parameters'
  | 'quality_events'
  | 'regulatory_links'
  | 'suggested_changes';

const TABS: Array<{ id: PharmaDiscoveryTab; label: string }> = [
  { id: 'scientific_entities', label: 'Scientific Entities' },
  { id: 'experiment_mapping', label: 'Experiment Mapping' },
  { id: 'batch_lineage', label: 'Batch Lineage' },
  { id: 'process_parameters', label: 'Process Parameters' },
  { id: 'quality_events', label: 'Quality Events' },
  { id: 'regulatory_links', label: 'Regulatory Links' },
  { id: 'suggested_changes', label: 'Suggested Ontology Changes' },
];

type Suggestion = {
  id: string;
  evidence: string;
  confidence: number;
  risk: 'low' | 'medium' | 'high';
  update: string;
  impact: string;
  approver: string;
};

const DEMO: Record<PharmaDiscoveryTab, Suggestion[]> = {
  scientific_entities: [
    {
      id: 'se-1',
      evidence: 'Analytical method transfer report AMTR-2025-014 §4.2 references “dissolution profile” as a quality attribute not yet in ontology.',
      confidence: 0.86,
      risk: 'low',
      update: 'Add entity AnalyticalMethodTransfer with attribute dissolution_profile_spec',
      impact: 'Drug Product subgraph; links to Analytical Test',
      approver: 'Ontology Steward',
    },
    {
      id: 'se-2',
      evidence: 'Stability summary tables label “supporting excursion” inconsistently with protocol SUP-88.',
      confidence: 0.71,
      risk: 'medium',
      update: 'Introduce StabilityExcursion node; synonym map “supporting excursion”',
      impact: 'Stability & CQA reporting',
      approver: 'Ontology Steward + QA review',
    },
  ],
  experiment_mapping: [
    {
      id: 'ex-1',
      evidence: 'DOE study DOE-LIQ-03 outcome tables tie factor ranges to blend uniformity—not modeled as experiment variables.',
      confidence: 0.79,
      risk: 'medium',
      update: 'Link ExperimentDesign → ProcessParameter with cardinal experiment_variable role',
      impact: 'Experiment graph; CPP ranges',
      approver: 'Ontology Steward',
    },
  ],
  batch_lineage: [
    {
      id: 'bl-1',
      evidence: 'Batch B-7721 master record references intermediate lot IL-22 not connected to finished lot L-9901 in graph projection.',
      confidence: 0.82,
      risk: 'high',
      update: 'Add transitive manufactured_from between Lot nodes with provenance on MR §7',
      impact: 'Batch lineage & recalls',
      approver: 'QA approval required',
    },
  ],
  process_parameters: [
    {
      id: 'pp-1',
      evidence: 'Granulation step G-12 lists “impeller RPM” with units RPM vs rev/min across three SOP revisions.',
      confidence: 0.77,
      risk: 'low',
      update: 'Canonical unit rev/min; map synonyms; classify as CPP candidate',
      impact: 'Process Flow graph; CPP governance',
      approver: 'Ontology Steward',
    },
  ],
  quality_events: [
    {
      id: 'qe-1',
      evidence: 'Deviation DV-2409 links CAPA CAPA-118 but ontology lacks impacts_batch edge type.',
      confidence: 0.88,
      risk: 'high',
      update: 'Add relationship deviation_impacts_batch (controlled predicate)',
      impact: 'Deviation Impact graph; audits',
      approver: 'QA approval required',
    },
  ],
  regulatory_links: [
    {
      id: 'rl-1',
      evidence: 'Process validation summary cites 21 CFR 211.110 — not linked to SOP PV-100 routing.',
      confidence: 0.69,
      risk: 'medium',
      update: 'Add regulatory_reference entity; link SOP → CFR citation',
      impact: 'Compliance narrative; regulatory interpretation queue',
      approver: 'Regulatory reviewer',
    },
  ],
  suggested_changes: [
    {
      id: 'so-1',
      evidence: 'Duplicate term “blend time” vs “mixing duration” in three batch records with identical CPP intent.',
      confidence: 0.91,
      risk: 'low',
      update: 'Synonym cluster + preferred label “blend_time_min”; retain locale variants',
      impact: 'Ontology normalization; low-risk additive',
      approver: 'Ontology Steward (auto-apply if policy allows)',
    },
  ],
};

function riskClass(r: Suggestion['risk']) {
  if (r === 'high') return 'border-[rgba(240,137,132,0.4)] text-[#f08984] bg-[rgba(240,137,132,0.12)]';
  if (r === 'medium') return 'border-[rgba(251,191,36,0.4)] text-[#facc15] bg-[rgba(251,191,36,0.1)]';
  return 'border-[rgba(62,207,155,0.4)] text-[#3ecf9b] bg-[rgba(62,207,155,0.12)]';
}

const PharmaOntologyDiscovery: React.FC = () => {
  const [tab, setTab] = useState<PharmaDiscoveryTab>('scientific_entities');
  const rows = DEMO[tab];

  return (
    <div className="rounded-xl border border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.07)] p-6 mb-8">
      <h2 className="text-lg font-semibold text-[#e8edf4] mb-1">Pharma-aware discovery</h2>
      <p className="text-sm text-[#8b9cb0] mb-4">
        Surfaces scientific gaps, lineage, parameters, quality events, and regulatory hooks using the same discovery pipeline—scoped to Drug Manufacturing.
      </p>
      <div className="flex flex-wrap gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === t.id
                ? 'bg-[rgba(167,139,250,0.25)] text-[#e8edf4] border border-[rgba(167,139,250,0.45)]'
                : 'border border-[rgba(148,163,184,0.2)] text-[#8b9cb0] hover:text-[#cbd5e1]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="space-y-4">
        {rows.map((s) => (
          <div
            key={s.id}
            className="rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] p-4 text-sm"
          >
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border ${riskClass(s.risk)}`}>
                Risk: {s.risk}
              </span>
              <span className="text-[10px] uppercase tracking-wide text-[#8b9cb0]">
                Confidence {Math.round(s.confidence * 100)}%
              </span>
            </div>
            <p className="text-[#8b9cb0] text-xs mb-2">
              <span className="font-semibold text-[#94a3b8]">Source evidence: </span>
              {s.evidence}
            </p>
            <p className="text-[#cbd5e1] mb-1">
              <span className="font-semibold text-[#e8edf4]">Suggested ontology update: </span>
              {s.update}
            </p>
            <p className="text-xs text-[#8b9cb0] mb-1">
              <span className="font-medium text-[#94a3b8]">Impact area: </span>
              {s.impact}
            </p>
            <p className="text-xs text-[#5ec8f2]">
              <span className="font-medium text-[#7dd3fc]">Recommended approver: </span>
              {s.approver}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PharmaOntologyDiscovery;
