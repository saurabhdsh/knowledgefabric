export type FabricKind =
  | 'general'
  | 'research'
  | 'healthcare'
  | 'life_sciences'
  | 'pharma_manufacturing'
  | 'insurance_claims'
  | 'mining_operations'
  | 'enterprise';

/** @deprecated Prefer FabricKind; kept for existing imports */
export type WeaveDomain = FabricKind | 'generic' | 'pharma';

export interface FabricKindOption {
  id: FabricKind;
  label: string;
  description: string;
  /** Shows pharma connector / artifact UI */
  showsPharmaWorkspace?: boolean;
}

export const FABRIC_KIND_OPTIONS: FabricKindOption[] = [
  {
    id: 'general',
    label: 'General Knowledge Fabric',
    description: 'Cross-domain documents and processes without a fixed industry lens.',
  },
  {
    id: 'research',
    label: 'Research Knowledge Fabric',
    description: 'Papers, studies, and technical research — evidence-aware synthesis.',
  },
  {
    id: 'healthcare',
    label: 'Healthcare',
    description: 'Clinical workflows, care pathways, and health-system operations.',
  },
  {
    id: 'life_sciences',
    label: 'Life Sciences',
    description: 'Discovery, translational science, and biotech R&D corpora.',
  },
  {
    id: 'pharma_manufacturing',
    label: 'Pharma Manufacturing',
    description: 'Batch records, quality, LIMS/MES/ELN, deviations and CAPA.',
    showsPharmaWorkspace: true,
  },
  {
    id: 'insurance_claims',
    label: 'Insurance & Claims',
    description: 'Claims adjudication, lifecycle, and insurance operations.',
  },
  {
    id: 'mining_operations',
    label: 'Mining Operations',
    description: 'Mine, fleet, rail, port, and site operations knowledge.',
  },
  {
    id: 'enterprise',
    label: 'Enterprise Operations',
    description: 'SOPs, ITSM/runbooks, and cross-functional playbooks.',
  },
];

const STORAGE_KEY = 'weave_domain';

const LEGACY_MAP: Record<string, FabricKind> = {
  generic: 'general',
  pharma: 'pharma_manufacturing',
};

export function normalizeFabricKind(raw: string | null | undefined): FabricKind {
  const v = String(raw || 'general').trim().toLowerCase().replace(/\s+/g, '_');
  const mapped = LEGACY_MAP[v] || v;
  if (FABRIC_KIND_OPTIONS.some((o) => o.id === mapped)) {
    return mapped as FabricKind;
  }
  return 'general';
}

export function getWeaveDomain(): FabricKind {
  try {
    return normalizeFabricKind(sessionStorage.getItem(STORAGE_KEY));
  } catch {
    return 'general';
  }
}

export function setWeaveDomain(domain: WeaveDomain): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, normalizeFabricKind(domain));
  } catch {
    /* ignore */
  }
}

export function fabricKindLabel(kind: string | null | undefined): string {
  const id = normalizeFabricKind(kind);
  return FABRIC_KIND_OPTIONS.find((o) => o.id === id)?.label || 'General Knowledge Fabric';
}

export function isPharmaManufacturing(kind: string | null | undefined): boolean {
  return normalizeFabricKind(kind) === 'pharma_manufacturing';
}
