import { isPharmaManufacturing, normalizeFabricKind, type WeaveDomain } from './weaveDomain';

export type PharmaGraphLens =
  | 'full'
  | 'drug_product'
  | 'batch_lineage'
  | 'experiment'
  | 'process_flow'
  | 'cqa_cpp'
  | 'deviation_impact'
  | 'sop_compliance';

export const PHARMA_GRAPH_VIEWS: Array<{ id: PharmaGraphLens; label: string; hint: string }> = [
  { id: 'full', label: 'Full graph', hint: 'All extracted entities and relations' },
  { id: 'drug_product', label: 'Drug Product', hint: 'Product, API, excipients, formulation' },
  { id: 'batch_lineage', label: 'Batch Lineage', hint: 'Lots, batches, genealogy' },
  { id: 'experiment', label: 'Experiment', hint: 'Studies, protocols, outcomes' },
  { id: 'process_flow', label: 'Process Flow', hint: 'Steps, equipment, parameters' },
  { id: 'cqa_cpp', label: 'CQA / CPP', hint: 'Critical quality attributes and parameters' },
  { id: 'deviation_impact', label: 'Deviation Impact', hint: 'Deviations, CAPA, affected batches' },
  { id: 'sop_compliance', label: 'SOP / Protocol Compliance', hint: 'Governing procedures and coverage' },
];

const LENS_PATTERNS: Record<Exclude<PharmaGraphLens, 'full'>, RegExp[]> = {
  drug_product: [/\bdrug\b/i, /\bproduct\b/i, /\bapi\b/i, /\bexcipient/i, /\bformulation/i],
  batch_lineage: [/\bbatch\b/i, /\blot\b/i, /\blineage\b/i, /\bmaterial\b/i],
  experiment: [/\bexperiment\b/i, /\bstudy\b/i, /\bprotocol\b/i, /\bassay\b/i],
  process_flow: [/\bstep\b/i, /\bprocess\b/i, /\bequipment\b/i, /\bparameter\b/i, /\bmfg\b/i],
  cqa_cpp: [/\bcqa\b/i, /\bcpp\b/i, /\bcritical\b/i, /\bquality attribute\b/i],
  deviation_impact: [/\bdeviation\b/i, /\bcapa\b/i, /\bncr\b/i, /\bimpact\b/i],
  sop_compliance: [/\bsop\b/i, /\bprocedure\b/i, /\bgovern/i, /\bcompliance\b/i],
};

export function labelMatchesPharmaLens(label: string, lens: PharmaGraphLens): boolean {
  if (lens === 'full') return true;
  const patterns = LENS_PATTERNS[lens];
  return patterns.some((re) => re.test(label));
}

export function isPharmaFabricFromDetails(details: { weave_domain?: string; tags?: string[] } | null): boolean {
  if (!details) return false;
  if (isPharmaManufacturing(details.weave_domain)) return true;
  const tags = details.tags || [];
  return tags.some((t) => /pharma|weave:pharma/i.test(String(t)));
}

export function shouldShowPharmaGraphUi(domain: WeaveDomain, details: { weave_domain?: string; tags?: string[] } | null): boolean {
  return isPharmaManufacturing(domain) || isPharmaFabricFromDetails(details);
}
