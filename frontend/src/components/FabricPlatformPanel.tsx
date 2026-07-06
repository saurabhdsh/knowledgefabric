import React, { useCallback, useEffect, useState } from 'react';
import { ArrowPathIcon, CheckCircleIcon, CubeIcon } from '@heroicons/react/24/outline';
import { jobStatusColor, jobTypeLabel, platformApi, PlatformJob } from '../utils/platformApi';

interface FabricPlatformPanelProps {
  fabricId: string;
  ontologyProjectId?: string | null;
  approvedOntologyVersionId?: string | null;
  onGraphUpdated?: () => void;
  compact?: boolean;
}

const FabricPlatformPanel: React.FC<FabricPlatformPanelProps> = ({
  fabricId,
  ontologyProjectId,
  approvedOntologyVersionId,
  onGraphUpdated,
  compact = false,
}) => {
  const [jobs, setJobs] = useState<PlatformJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const loadJobs = useCallback(async () => {
    try {
      const data = await platformApi.listFabricJobs(fabricId);
      setJobs(data);
      const active = data.some((j) => ['queued', 'running', 'indexing', 'training'].includes(j.status));
      setPolling(active);
    } catch {
      setJobs([]);
    }
  }, [fabricId]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    if (!polling) return undefined;
    const t = setInterval(loadJobs, 2500);
    return () => clearInterval(t);
  }, [polling, loadJobs]);

  const runDiscover = async () => {
    try {
      setLoading(true);
      setActionError(null);
      setActionMessage(null);
      const { job_id } = await platformApi.discoverOntology(fabricId);
      setActionMessage(`Ontology discovery queued (${job_id})`);
      setPolling(true);
      await loadJobs();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Discovery failed');
    } finally {
      setLoading(false);
    }
  };

  const runGraphBuild = async () => {
    if (!approvedOntologyVersionId) {
      setActionError('Approve an ontology version first.');
      return;
    }
    try {
      setLoading(true);
      setActionError(null);
      const result = await platformApi.buildGraph(fabricId, approvedOntologyVersionId, true);
      setActionMessage(`Graph build queued (${String(result.job_id || 'job')})`);
      setPolling(true);
      await loadJobs();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Graph build failed');
    } finally {
      setLoading(false);
    }
  };

  const runExport = async (targets: Array<'neo4j' | 'rdf' | 'stardog'>) => {
    if (!approvedOntologyVersionId) return;
    try {
      setLoading(true);
      setActionError(null);
      await platformApi.exportGraph(fabricId, approvedOntologyVersionId, targets);
      setActionMessage(`Export to ${targets.join(', ')} completed`);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const finished = jobs.find(
      (j) => j.job_type === 'graph_build' && j.status === 'ready' && j.completed_at,
    );
    if (finished && onGraphUpdated) onGraphUpdated();
  }, [jobs, onGraphUpdated]);

  return (
    <div className={`rounded-xl border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.06)] ${compact ? 'p-3' : 'p-4 mb-4'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <p className="text-sm font-semibold text-[#e8edf4] flex items-center gap-2">
            <CubeIcon className="h-4 w-4 text-[#5ec8f2]" />
            Enterprise platform
          </p>
          <p className="text-xs text-[#8b9cb0] mt-0.5">
            Ontology discovery → approval → canonical knowledge graph
          </p>
        </div>
        <button
          type="button"
          onClick={loadJobs}
          className="inline-flex items-center gap-1 rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1 text-[11px] text-[#cbd5e1] hover:bg-white/[0.05]"
        >
          <ArrowPathIcon className="h-3.5 w-3.5" />
          Refresh jobs
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs mb-3">
        <div className="rounded-lg border border-[rgba(148,163,184,0.15)] bg-white/[0.03] px-3 py-2">
          <span className="text-[#8b9cb0]">Ontology project</span>
          <p className="font-mono text-[#cbd5e1] truncate">{ontologyProjectId || '—'}</p>
        </div>
        <div className="rounded-lg border border-[rgba(148,163,184,0.15)] bg-white/[0.03] px-3 py-2">
          <span className="text-[#8b9cb0]">Approved version</span>
          <p className="font-mono text-[#cbd5e1] truncate">{approvedOntologyVersionId || '—'}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        <button
          type="button"
          disabled={loading}
          onClick={runDiscover}
          className="rounded-lg border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)] px-3 py-1.5 text-xs text-[#cfefff] disabled:opacity-50"
        >
          Run ontology discovery
        </button>
        <button
          type="button"
          disabled={loading || !approvedOntologyVersionId}
          onClick={runGraphBuild}
          className="rounded-lg border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.12)] px-3 py-1.5 text-xs text-[#bdf5dd] disabled:opacity-50"
        >
          Build canonical graph
        </button>
        <button
          type="button"
          disabled={loading || !approvedOntologyVersionId}
          onClick={() => runExport(['rdf'])}
          className="rounded-lg border border-[rgba(148,163,184,0.25)] bg-white/[0.04] px-3 py-1.5 text-xs text-[#cbd5e1] disabled:opacity-50"
        >
          Export RDF
        </button>
        <button
          type="button"
          disabled={loading || !approvedOntologyVersionId}
          onClick={() => runExport(['neo4j'])}
          className="rounded-lg border border-[rgba(148,163,184,0.25)] bg-white/[0.04] px-3 py-1.5 text-xs text-[#cbd5e1] disabled:opacity-50"
        >
          Export Neo4j
        </button>
      </div>

      {actionMessage && (
        <p className="text-xs text-[#3ecf9b] mb-2 flex items-center gap-1">
          <CheckCircleIcon className="h-3.5 w-3.5" />
          {actionMessage}
        </p>
      )}
      {actionError && <p className="text-xs text-[#fca5a5] mb-2">{actionError}</p>}

      {jobs.length > 0 && (
        <div className="space-y-1.5 max-h-36 overflow-auto">
          {jobs.slice(0, 6).map((job) => (
            <div
              key={job.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0b0f16]/50 px-2 py-1.5 text-[11px]"
            >
              <span className="text-[#cbd5e1]">{jobTypeLabel(job.job_type)}</span>
              <span className={`px-2 py-0.5 rounded-full border ${jobStatusColor(job.status)}`}>
                {job.status} {job.progress_percent > 0 ? `${Math.round(job.progress_percent)}%` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FabricPlatformPanel;
