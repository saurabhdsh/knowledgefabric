/**
 * Weave enterprise platform API (jobs, ontology approval, canonical graph).
 */
import { apiRequest } from './api';

const PLATFORM_BASE = 'api/v1/platform';
const GRAPH_BASE = 'api/v1/graph';

export interface PlatformJob {
  id: string;
  fabric_id?: string | null;
  job_type: string;
  status: string;
  progress_percent: number;
  error_payload?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  config?: Record<string, unknown>;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
}

async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.error || payload?.message || `Request failed (${response.status})`);
  }
  return (payload?.data ?? payload) as T;
}

export const platformApi = {
  async getJob(jobId: string): Promise<PlatformJob> {
    const res = await apiRequest(`${PLATFORM_BASE}/jobs/${jobId}`);
    return parseJson<PlatformJob>(res);
  },

  async listFabricJobs(fabricId: string): Promise<PlatformJob[]> {
    const res = await apiRequest(`${PLATFORM_BASE}/fabrics/${fabricId}/jobs`);
    return parseJson<PlatformJob[]>(res);
  },

  async discoverOntology(fabricId: string, useLlm = true): Promise<{ job_id: string }> {
    const res = await apiRequest(`${PLATFORM_BASE}/fabrics/${fabricId}/discover-ontology?use_llm=${useLlm}`, {
      method: 'POST',
    });
    return parseJson<{ job_id: string }>(res);
  },

  async approveOntologyVersion(
    versionId: string,
    options?: { approved_by?: string; trigger_graph_build?: boolean; storage_backend?: string },
  ): Promise<{ version_id: string; fabric_id?: string; graph_build_job_id?: string }> {
    const res = await apiRequest(`${GRAPH_BASE}/ontology/versions/${versionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approved_by: options?.approved_by ?? 'analyst',
        trigger_graph_build: options?.trigger_graph_build ?? true,
        storage_backend: options?.storage_backend,
      }),
    });
    return parseJson(res);
  },

  async buildGraph(
    fabricId: string,
    ontologyVersionId: string,
    asyncJob = true,
    storageBackend?: string,
  ): Promise<Record<string, unknown>> {
    const res = await apiRequest(`${GRAPH_BASE}/fabrics/${fabricId}/graph/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ontology_version_id: ontologyVersionId,
        async_job: asyncJob,
        storage_backend: storageBackend,
      }),
    });
    return parseJson(res);
  },

  async getCanonicalGraph(
    fabricId: string,
    ontologyVersionId?: string,
  ): Promise<Record<string, unknown>> {
    const qs = ontologyVersionId ? `?ontology_version_id=${encodeURIComponent(ontologyVersionId)}` : '';
    const res = await apiRequest(`${GRAPH_BASE}/fabrics/${fabricId}/graph${qs}`);
    return parseJson(res);
  },

  async exportGraph(
    fabricId: string,
    ontologyVersionId: string,
    targets: Array<'neo4j' | 'rdf' | 'stardog'>,
  ): Promise<Record<string, unknown>> {
    const res = await apiRequest(`${GRAPH_BASE}/fabrics/${fabricId}/graph/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ontology_version_id: ontologyVersionId, targets }),
    });
    return parseJson(res);
  },
};

export function jobStatusColor(status: string): string {
  switch (status) {
    case 'ready':
    case 'completed':
      return 'text-[#3ecf9b] border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)]';
    case 'running':
    case 'indexing':
    case 'training':
      return 'text-[#5ec8f2] border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.14)]';
    case 'failed':
      return 'text-[#f08984] border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.14)]';
    default:
      return 'text-[#8b9cb0] border-[rgba(148,163,184,0.2)] bg-white/[0.03]';
  }
}

export function jobTypeLabel(jobType: string): string {
  const labels: Record<string, string> = {
    ontology_discovery: 'Ontology discovery',
    graph_build: 'Graph build',
    graph_export: 'Graph export',
    fabric_ingest: 'Fabric ingest',
  };
  return labels[jobType] || jobType;
}
