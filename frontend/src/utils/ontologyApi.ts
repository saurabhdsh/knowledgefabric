/**
 * Ontology Discovery API client.
 * Uses configured backend URL (REACT_APP_API_URL) with localhost fallback.
 */
import { getApiUrl } from './api';
import { getAuthHeaders } from './authStorage';

const ONTOLOGY_BASE = 'api/v1/ontology';

export interface OntologyProject {
  id: string;
  name: string;
  description?: string;
  domain?: string;
  source_artifacts: Array<{
    id: string;
    file_name: string;
    file_path?: string;
    source_type: string;
    metadata?: Record<string, unknown>;
  }>;
  current_version_id?: string;
  version_ids: string[];
  created_at?: string;
  updated_at?: string;
}

export interface OntologyClass {
  id: string;
  name: string;
  normalized_name: string;
  definition?: string;
  aliases?: string[];
  source_evidence: Array<{ text_snippet?: string; page_number?: number; xml_path?: string; artifact_type?: string; extraction_stage?: string }>;
  confidence_score: number;
  status: string;
  extraction_source?: string;
}

export interface OntologyRelationship {
  id: string;
  source_class_id: string;
  relationship_name: string;
  target_class_id: string;
  definition?: string;
  cardinality_if_detected?: string;
  confidence_score: number;
  status: string;
  evidence?: Array<{ text_snippet?: string; page_number?: number; xml_path?: string; artifact_type?: string; extraction_stage?: string }>;
  extraction_source?: string;
}

export interface OntologyAttribute {
  id: string;
  class_id: string;
  attribute_name: string;
  normalized_name: string;
  data_type_guess?: string;
  required_flag_guess: boolean;
  description?: string;
  confidence_score: number;
  status: string;
  evidence?: Array<{ text_snippet?: string; page_number?: number; xml_path?: string; artifact_type?: string; extraction_stage?: string }>;
  extraction_source?: string;
}

export interface OntologyVersion {
  id: string;
  project_id: string;
  version_label: string;
  is_draft: boolean;
  classes: OntologyClass[];
  relationships: OntologyRelationship[];
  attributes: OntologyAttribute[];
  constraints: Array<{ id: string; constraint_type: string; expression: string }>;
  created_at?: string;
  updated_at?: string;
}

export interface DiscoveryRun {
  id: string;
  project_id: string;
  status: string;
  current_stage?: string;
  progress_percent: number;
  result_version_id?: string;
  error_message?: string;
  run_logs: Array<{ stage?: string; message?: string }>;
  started_at?: string;
  completed_at?: string;
}

export interface EnrichmentCandidate {
  id: string;
  sourceDatasetId: string;
  changeType: string;
  suggestedEntity?: string;
  suggestedAttribute?: string;
  suggestedRelationship?: string;
  currentOntologyMatch?: string;
  classification: string[];
  businessDomain: string;
  sensitivity: string;
  riskLevel: string;
  confidenceScore: number;
  recommendation: string;
  aiRationale: string;
  policyDecision?: string;
  status: string;
  createdBy: string;
  reviewedBy?: string;
  reviewedAt?: string;
  promotedVersion?: string;
  lineage: Record<string, unknown>;
  evidence: Record<string, unknown>;
  createdAt?: string;
  updatedAt?: string;
}

export interface OntologyVersionRecord {
  id: string;
  versionNumber: string;
  environment: string;
  changeSummary: string;
  changeIds: string[];
  approvedBy?: string;
  createdAt?: string;
  rollbackReference?: string;
  status: string;
  snapshot: Record<string, unknown>;
}

export interface KnowledgeFabricLite {
  id: string;
  name: string;
  source_type?: string;
  document_count?: number;
}

export interface AgentQueryResult {
  element_id: string;
  element_type: string;
  element_name: string;
  rank_score: number;
  citations: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
}

export interface AgentContract {
  contract_id: string;
  name: string;
  version: string;
  description?: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  compatibility: string;
  owner: string;
  tags: string[];
  created_at?: string;
  updated_at?: string;
}

async function apiGet<T>(path: string): Promise<T> {
  const endpoint = `${ONTOLOGY_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
  const url = path.startsWith('http') ? path : getApiUrl(endpoint);
  const res = await fetch(url, { cache: 'no-store', headers: getAuthHeaders() });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiPost<T>(path: string, body?: object): Promise<T> {
  const url = getApiUrl(`${ONTOLOGY_BASE}${path.startsWith('/') ? '' : '/'}${path}`);
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiPut<T>(path: string, body: object): Promise<T> {
  const url = getApiUrl(`${ONTOLOGY_BASE}${path.startsWith('/') ? '' : '/'}${path}`);
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

export const ontologyApi = {
  listProjects: () => apiGet<{ success: boolean; data: OntologyProject[] }>('/projects').then(r => r.data),
  createProject: (name: string, description?: string, domain?: string) =>
    apiPost<{ success: boolean; data: OntologyProject }>('/projects', { name, description, domain }).then(r => r.data),
  createProjectFromFabric: (fabricId: string, name?: string, description?: string, domain?: string) =>
    apiPost<{ success: boolean; data: OntologyProject & { fabric_reference?: Record<string, unknown> } }>('/projects/from-fabric', {
      fabric_id: fabricId,
      name,
      description,
      domain,
    }).then(r => r.data),
  getProject: (projectId: string) =>
    apiGet<{ success: boolean; data: OntologyProject }>(`/projects/${projectId}`).then(r => r.data),
  deleteProject: async (projectId: string) => {
    const url = getApiUrl(`${ONTOLOGY_BASE}/projects/${projectId}/delete`);
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  getAvailableArtifacts: () =>
    apiGet<{ success: boolean; data: Array<{ name: string; path: string; size: number }> }>('/artifacts/available').then(r => r.data),
  uploadDocuments: async (files: File[]) => {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    const url = getApiUrl(`${ONTOLOGY_BASE}/upload`);
    const res = await fetch(url, { method: 'POST', body: form, headers: getAuthHeaders() });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  discover: (projectId: string, artifactIds: string[], useLlm = true) =>
    apiPost<{ success: boolean; data: { run_id: string; status: string } }>(`/projects/${projectId}/discover`, {
      project_id: projectId,
      artifact_ids: artifactIds,
      use_llm: useLlm,
    }).then(r => r.data),
  listRuns: (projectId: string) =>
    apiGet<{ success: boolean; data: DiscoveryRun[] }>(`/projects/${projectId}/runs`).then(r => r.data),
  getRun: (projectId: string, runId: string) =>
    apiGet<{ success: boolean; data: DiscoveryRun }>(`/projects/${projectId}/runs/${runId}`).then(r => r.data),
  listVersions: (projectId: string) =>
    apiGet<{ success: boolean; data: Array<{ id: string; version_label: string; is_draft: boolean }> }>(`/projects/${projectId}/versions`).then(r => r.data),
  getVersion: (projectId: string, versionId: string) =>
    apiGet<{ success: boolean; data: OntologyVersion }>(`/projects/${projectId}/versions/${versionId}`).then(r => r.data),
  updateClass: (classId: string, body: Partial<{ name: string; normalized_name: string; definition: string; status: string }>) =>
    apiPut<{ success: boolean; data: OntologyClass }>(`/classes/${classId}`, body),
  updateRelationship: (relId: string, body: Partial<{ relationship_name: string; definition: string; cardinality_if_detected: string; status: string }>) =>
    apiPut<{ success: boolean; data: OntologyRelationship }>(`/relationships/${relId}`, body),
  updateAttribute: (attrId: string, body: Partial<{ attribute_name: string; normalized_name: string; data_type_guess: string; required_flag_guess: boolean; status: string }>) =>
    apiPut<{ success: boolean; data: OntologyAttribute }>(`/attributes/${attrId}`, body),
  reviewApprove: (versionId: string, elementType: string, elementIds: string[]) =>
    apiPost('/review/approve', { version_id: versionId, element_type: elementType, element_ids: elementIds }),
  reviewReject: (versionId: string, elementType: string, elementIds: string[], reason?: string) =>
    apiPost('/review/reject', { version_id: versionId, element_type: elementType, element_ids: elementIds, reason }),
  merge: (versionId: string, sourceClassIds: string[], targetClassId: string) =>
    apiPost('/merge', { version_id: versionId, source_class_ids: sourceClassIds, target_class_id: targetClassId }),
  exportJson: (versionId: string) =>
    fetch(getApiUrl(`${ONTOLOGY_BASE}/export/${versionId}?format=json`), { headers: getAuthHeaders() }).then(r => r.json()),
  exportCsvUrl: (versionId: string) => getApiUrl(`${ONTOLOGY_BASE}/export/${versionId}?format=csv`),
  exportGraph: (versionId: string) =>
    fetch(getApiUrl(`${ONTOLOGY_BASE}/export/${versionId}?format=graph`), { headers: getAuthHeaders() }).then(r => r.json()),
  exportCanonical: (versionId: string) =>
    apiGet<{ success: boolean; data: object }>(`/export/${versionId}/canonical`).then(r => r.data),
  /** Real-time Q&A using OpenAI. context = selected element summary for the model. */
  chat: (
    versionId: string | null,
    message: string,
    context?: { selected_type: string; selected_name: string; selected_summary: string },
    history?: Array<{ role: string; content: string }>,
  ) =>
    apiPost<{ success: boolean; data: { reply: string } }>('/chat', {
      version_id: versionId ?? undefined,
      message,
      context,
      history,
    }).then(r => r.data),
  discoverEnrichment: (payload: { source_dataset_id: string; fields: Array<Record<string, unknown>>; metadata?: Record<string, unknown>; created_by?: string }) =>
    apiPost<{ success: boolean; data: EnrichmentCandidate[] }>('/enrichment/discover', payload).then(r => r.data),
  discoverEnrichmentFromProject: (payload: { project_id: string; version_id?: string; created_by?: string }) =>
    apiPost<{ success: boolean; data: EnrichmentCandidate[] }>('/enrichment/discover-from-project', payload).then(r => r.data),
  listCandidates: () =>
    apiGet<{ success: boolean; data: EnrichmentCandidate[] }>('/enrichment/candidates').then(r => r.data),
  getCandidate: (candidateId: string) =>
    apiGet<{ success: boolean; data: { candidate: EnrichmentCandidate; policy_logs: Array<Record<string, unknown>> } }>(`/enrichment/candidates/${candidateId}`).then(r => r.data),
  approveCandidate: (candidateId: string, reviewer: string, notes?: string) =>
    apiPost<{ success: boolean; data: EnrichmentCandidate }>(`/enrichment/candidates/${candidateId}/approve`, { reviewer, notes }).then(r => r.data),
  rejectCandidate: (candidateId: string, reviewer: string, notes?: string) =>
    apiPost<{ success: boolean; data: EnrichmentCandidate }>(`/enrichment/candidates/${candidateId}/reject`, { reviewer, notes }).then(r => r.data),
  requestCandidateEvidence: (candidateId: string, reviewer: string, notes?: string) =>
    apiPost<{ success: boolean; data: EnrichmentCandidate }>(`/enrichment/candidates/${candidateId}/request-evidence`, { reviewer, notes }).then(r => r.data),
  promoteCandidate: (candidateId: string, reviewer: string, notes?: string) =>
    apiPost<{ success: boolean; data: { candidate: EnrichmentCandidate; version: OntologyVersionRecord } }>(`/enrichment/candidates/${candidateId}/promote`, { reviewer, notes }).then(r => r.data),
  evaluatePolicy: (candidate: Record<string, unknown>) =>
    apiPost<{ success: boolean; data: Record<string, unknown> }>('/enrichment/policy/evaluate', candidate).then(r => r.data),
  listOntologyVersions: () =>
    apiGet<{ success: boolean; data: OntologyVersionRecord[] }>('/versions').then(r => r.data),
  getOntologyVersion: (versionId: string) =>
    apiGet<{ success: boolean; data: OntologyVersionRecord }>(`/versions/${versionId}`).then(r => r.data),
  rollbackOntologyVersion: (versionId: string, reviewer: string, notes?: string) =>
    apiPost<{ success: boolean; data: OntologyVersionRecord }>(`/versions/${versionId}/rollback`, { reviewer, notes }).then(r => r.data),
  compareOntologyVersions: (fromVersion: string, toVersion: string) =>
    apiGet<{ success: boolean; data: Record<string, unknown> }>(`/compare?fromVersion=${encodeURIComponent(fromVersion)}&toVersion=${encodeURIComponent(toVersion)}`).then(r => r.data),
  getGovernanceMode: () =>
    apiGet<{ success: boolean; data: { mode: string } }>('/settings/governance-mode').then(r => r.data),
  updateGovernanceMode: (mode: 'manual' | 'assisted' | 'controlled_auto_apply', updatedBy = 'admin') =>
    apiPut<{ success: boolean; data: { governance_mode: string; updated_by: string; updated_at: string } }>('/settings/governance-mode', { mode, updated_by: updatedBy }).then(r => r.data),
  agentQuery: (payload: { project_id: string; version_id: string; query: string; top_k?: number; role?: string; include_debug?: boolean }) =>
    apiPost<{ success: boolean; data: { answer_preview: string; generated_query: Record<string, unknown>; results: AgentQueryResult[]; trust_score: Record<string, unknown>; debug?: Record<string, unknown> } }>('/agent/query', payload).then(r => r.data),
  listAgentContracts: () =>
    apiGet<{ success: boolean; data: AgentContract[] }>('/agent/contracts').then(r => r.data),
  upsertAgentContract: (payload: {
    contract_id: string;
    name: string;
    version: string;
    description?: string;
    input_schema?: Record<string, unknown>;
    output_schema?: Record<string, unknown>;
    compatibility?: string;
    owner?: string;
    tags?: string[];
  }) => apiPost<{ success: boolean; data: AgentContract }>('/agent/contracts', payload).then(r => r.data),
  deleteAgentContract: async (contractId: string, version: string) => {
    // POST matches project delete pattern — some SPA/proxy setups mishandle DELETE.
    const res = await fetch(getApiUrl(`${ONTOLOGY_BASE}/agent/contracts/delete`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ contract_id: contractId, version }),
    });
    const text = await res.text();
    let payload: { success?: boolean; message?: string; detail?: string | unknown };
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(text || `HTTP ${res.status}`);
    }
    if (!res.ok) {
      const detail =
        typeof payload.detail === 'string'
          ? payload.detail
          : typeof payload.message === 'string'
            ? payload.message
            : text;
      throw new Error(detail || `HTTP ${res.status}`);
    }
    if (payload.success === false) {
      throw new Error(typeof payload.message === 'string' ? payload.message : 'Delete failed');
    }
    return payload as { success: boolean; data?: { contract_id: string; version: string } };
  },
  getAgentTrustScore: (projectId: string, versionId: string, elementId?: string) =>
    apiGet<{ success: boolean; data: Record<string, unknown> }>(`/agent/trust-score/${encodeURIComponent(projectId)}/${encodeURIComponent(versionId)}${elementId ? `?element_id=${encodeURIComponent(elementId)}` : ''}`).then(r => r.data),
  evaluateAgentPolicy: (payload: { role: string; purpose?: string; payload: Record<string, unknown>; strict_mode?: boolean }) =>
    apiPost<{ success: boolean; data: Record<string, unknown> }>('/agent/policy/evaluate', payload).then(r => r.data),
  listKnowledgeFabrics: async () => {
    const res = await fetch(getApiUrl('api/v1/knowledge/'), { headers: getAuthHeaders() });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || `HTTP ${res.status}`);
    }
    const payload = await res.json();
    return (payload?.data || []) as KnowledgeFabricLite[];
  },
};
