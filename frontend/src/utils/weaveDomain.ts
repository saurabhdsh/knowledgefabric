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

/** Ingestion pipes Weave actually supports today. */
export type FabricSourceId = 'pdf' | 'database' | 'servicenow' | 'codebase' | 'composite';

export interface KindSourceCatalog {
  /** Shown first under “Recommended for this kind”. */
  recommended: FabricSourceId[];
  /** Shown under “Other sources” (empty = no secondary section). */
  other: FabricSourceId[];
  /** Optional title/description overrides keyed by source id. */
  copy?: Partial<Record<FabricSourceId, { title: string; description: string }>>;
}

/**
 * Kind drives which sources are recommended. Same pipes underneath —
 * no invented connectors appear here.
 */
export const KIND_SOURCE_CATALOG: Record<FabricKind, KindSourceCatalog> = {
  general: {
    recommended: ['pdf', 'database', 'servicenow', 'codebase', 'composite'],
    other: [],
  },
  research: {
    recommended: ['pdf', 'database', 'composite'],
    other: ['servicenow', 'codebase'],
    copy: {
      pdf: {
        title: 'Papers & research reports',
        description: 'PDFs of studies, preprints, and technical reports — evidence-aware chunking',
      },
      database: {
        title: 'Study tables & extracts',
        description: 'CSV / SQL exports of results tables, registries, and supplementary data',
      },
      composite: {
        title: 'Papers + data composite',
        description: 'Merge an existing paper fabric with a table fabric for one research graph',
      },
      servicenow: {
        title: 'Ops / ticket export',
        description: 'Only if your research ops run through ITSM — prefer an export upload',
      },
      codebase: {
        title: 'Methods / analysis code',
        description: 'Optional: analysis scripts or pipelines that support the papers',
      },
    },
  },
  life_sciences: {
    recommended: ['pdf', 'database', 'composite'],
    other: ['servicenow', 'codebase'],
    copy: {
      pdf: {
        title: 'Scientific documents',
        description: 'Discovery reports, protocols, and translational write-ups',
      },
      database: {
        title: 'Assay & ELN extracts',
        description: 'Assay tables, ELN exports, and structured lab results',
      },
      composite: {
        title: 'Docs + assay composite',
        description: 'Unify document and structured fabrics for one life-sciences graph',
      },
    },
  },
  healthcare: {
    recommended: ['pdf', 'database', 'composite'],
    other: ['servicenow', 'codebase'],
    copy: {
      pdf: {
        title: 'Clinical & pathway documents',
        description: 'Care pathways, guidelines, and operational clinical PDFs',
      },
      database: {
        title: 'Clinical / claims-style tables',
        description: 'Member, encounter, or claims extracts as CSV or SQL',
      },
      composite: {
        title: 'Docs + records composite',
        description: 'Combine pathway documents with structured patient/ops tables',
      },
      servicenow: {
        title: 'Care-ops ITSM export',
        description: 'Incident or request exports when care ops run through ITSM',
      },
    },
  },
  pharma_manufacturing: {
    recommended: ['pdf', 'database', 'servicenow', 'composite'],
    other: ['codebase'],
    copy: {
      pdf: {
        title: 'Batch records, SOPs & CoAs',
        description: 'BMR, SOP, CoA, protocol, and quality documentation PDFs',
      },
      database: {
        title: 'LIMS / MES / ELN exports',
        description: 'Structured manufacturing and lab tables (CSV or live SQL where configured)',
      },
      servicenow: {
        title: 'Deviation & CAPA exports',
        description: 'Quality events as spreadsheet or labelled sample — not a fake live instance',
      },
      composite: {
        title: 'Manufacturing composite',
        description: 'Unify docs, LIMS/MES, and quality-event fabrics into one governed fabric',
      },
      codebase: {
        title: 'Automation / recipe code',
        description: 'Optional scripts or recipe automation that support the plant systems',
      },
    },
  },
  insurance_claims: {
    recommended: ['database', 'pdf', 'composite'],
    other: ['servicenow', 'codebase'],
    copy: {
      database: {
        title: 'Claims & policy tables',
        description: 'Claims, members, providers, and policy extracts (CSV / SQL)',
      },
      pdf: {
        title: 'Guidelines & policy PDFs',
        description: 'Adjudication guides, policy booklets, and ops manuals',
      },
      composite: {
        title: 'Claims + guidelines composite',
        description: 'Merge structured claims with guideline document fabrics',
      },
      servicenow: {
        title: 'Claims-ops ITSM export',
        description: 'Only when claim work is tracked in ITSM — use an export',
      },
    },
  },
  mining_operations: {
    recommended: ['pdf', 'database', 'composite'],
    other: ['servicenow', 'codebase'],
    copy: {
      pdf: {
        title: 'Site SOPs & shift reports',
        description: 'Mine, rail, port, and site operating documents',
      },
      database: {
        title: 'Fleet & ops tables',
        description: 'Equipment, production, and logistics extracts',
      },
      composite: {
        title: 'Site ops composite',
        description: 'Combine documents and ops tables for one site graph',
      },
    },
  },
  enterprise: {
    recommended: ['pdf', 'servicenow', 'codebase', 'composite'],
    other: ['database'],
    copy: {
      pdf: {
        title: 'SOPs & playbooks',
        description: 'Standard operating procedures, runbooks, and policy PDFs',
      },
      servicenow: {
        title: 'ITSM / runbook exports',
        description: 'Incidents, changes, and knowledge-article exports',
      },
      codebase: {
        title: 'Platform / service codebase',
        description: 'Repos and services that the runbooks operate on',
      },
      composite: {
        title: 'Ops composite',
        description: 'Unify SOP, ITSM, and code fabrics for enterprise ops',
      },
      database: {
        title: 'Ops data tables',
        description: 'CMDB-style or ops warehouse extracts when you have them',
      },
    },
  },
};

export function sourceCatalogForKind(kind: string | null | undefined): KindSourceCatalog {
  return KIND_SOURCE_CATALOG[normalizeFabricKind(kind)];
}
