import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DocumentTextIcon,
  ServerIcon,
  BeakerIcon,
  GlobeAltIcon,
  TrashIcon,
  EyeIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  PencilSquareIcon,
  CodeBracketSquareIcon,
} from '@heroicons/react/24/outline';
import FabricEndpointsDialog from '../components/FabricEndpointsDialog';
import { apiRequest, authenticatedFetch, getApiUrl } from '../utils/api';
import { getAuthHeaders } from '../utils/authStorage';
import { jobStatusColor, jobTypeLabel, platformApi, PlatformJob } from '../utils/platformApi';
import { fabricKindLabel } from '../utils/weaveDomain';

interface KnowledgeFabric {
  id: string;
  name: string;
  source_type: string;
  description?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  document_count: number;
  total_chunks?: number;
  status: string;
  model_status?: string;
  last_training?: string;
  weave_domain?: string;
  ontology_project_id?: string | null;
  approved_ontology_version_id?: string | null;
  pipeline?: {
    version?: number;
    status?: string;
    stages?: Array<{ name: string; status: string }>;
  } | null;
}

const Fabrics: React.FC = () => {
  const navigate = useNavigate();
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showEndpointsDialog, setShowEndpointsDialog] = useState(false);
  const [selectedFabricForEndpoints, setSelectedFabricForEndpoints] = useState<KnowledgeFabric | null>(null);
  const [fabricJobs, setFabricJobs] = useState<Record<string, PlatformJob[]>>({});
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'failed' | 'building' | 'indexed'>('all');
  const [deleteCard, setDeleteCard] = useState<{
    fabric: KnowledgeFabric;
    phase: 'deleting' | 'deleted' | 'error';
    message?: string;
  } | null>(null);
  const deletedIdsRef = useRef<Set<string>>(new Set());
  const deletingIdRef = useRef<string | null>(null);

  const applyFabricList = (list: KnowledgeFabric[]) => {
    const hidden = deletedIdsRef.current;
    const inflight = deletingIdRef.current;
    setFabrics(list.filter((fabric) => !hidden.has(fabric.id) && fabric.id !== inflight));
  };

  const fetchFabricsFromApi = async () => {
    const response = await apiRequest('api/v1/knowledge/');
    if (!response.ok) return null;
    const data = await response.json();
    if (data.success && data.data) return data.data as KnowledgeFabric[];
    return null;
  };

  const loadFabricJobs = async (fabricId: string) => {
    try {
      const jobs = await platformApi.listFabricJobs(fabricId);
      setFabricJobs((prev) => ({ ...prev, [fabricId]: jobs }));
    } catch {
      /* optional */
    }
  };
  useEffect(() => {
    const fetchFabrics = async (options?: { silent?: boolean }) => {
      const isSilent = options?.silent ?? false;
      try {
        if (isSilent) {
          setRefreshing(true);
        } else {
          setInitialLoading(true);
        }

        const list = await fetchFabricsFromApi();
        if (list) {
          applyFabricList(list);
          list.slice(0, 6).forEach((f) => loadFabricJobs(f.id));
        } else {
          setFabrics([]);
        }
      } catch (error) {
        console.error('Error fetching fabrics:', error);
        setFabrics([]);
      } finally {
        if (isSilent) {
          setRefreshing(false);
        } else {
          setInitialLoading(false);
        }
      }
    };

    fetchFabrics();
    
    // Refresh data every 10 seconds to get updated training status
    const interval = setInterval(() => {
      fetchFabrics({ silent: true });
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      const list = await fetchFabricsFromApi();
      if (list) applyFabricList(list);
    } catch (error) {
      console.error('Error refreshing fabrics:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b]';
      case 'building':
      case 'training':
        return 'border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.14)] text-[#5ec8f2]';
      case 'failed':
      case 'error':
        return 'border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.14)] text-[#f08984]';
      default:
        return 'border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#8b9cb0]';
    }
  };

  const getSourceTypeIcon = (sourceType: string) => {
    switch (sourceType) {
      case 'pdf':
        return <DocumentTextIcon className="h-4 w-4" />;
      case 'database':
        return <ServerIcon className="h-4 w-4" />;
      case 'codebase':
        return <CodeBracketSquareIcon className="h-4 w-4" />;
      case 'mixed':
      case 'composite':
        return <BeakerIcon className="h-4 w-4" />;
      default:
        return <GlobeAltIcon className="h-4 w-4" />;
    }
  };

  const parseApiDate = (raw: string): Date | null => {
    if (!raw) return null;
    const trimmed = raw.trim();
    // Backend often returns UTC timestamps without timezone marker.
    // If timezone is missing, treat it as UTC so local display is correct.
    const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(trimmed);
    const normalized = hasTimezone ? trimmed : `${trimmed}Z`;
    const parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const formatDate = (dateString: string) => {
    const parsed = parseApiDate(dateString);
    if (!parsed) return dateString;
    return parsed.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleViewFabric = (fabric: KnowledgeFabric) => {
    navigate(`/fabrics/${fabric.id}/knowledge-graph`);
  };

  useEffect(() => {
    if (deleteCard?.phase !== 'deleted') return;
    const timer = window.setTimeout(() => setDeleteCard(null), 1100);
    return () => window.clearTimeout(timer);
  }, [deleteCard]);

  const handleDeleteFabric = async (fabric: KnowledgeFabric) => {
    if (deletingIdRef.current) return;
    deletingIdRef.current = fabric.id;
    setDeleteCard({ fabric, phase: 'deleting' });
    setFabrics((prev) => prev.filter((item) => item.id !== fabric.id));
    try {
      const response = await authenticatedFetch(getApiUrl(`api/v1/knowledge/${fabric.id}`), {
        method: 'DELETE',
      });
      const payload = await response.json().catch(() => ({} as { success?: boolean; message?: string; detail?: unknown }));
      const detail = typeof payload.detail === 'string' ? payload.detail : '';
      const message = detail || payload.message || '';
      const explicitFailure = payload.success === false || /failed to delete/i.test(message);
      const removed = !explicitFailure && (response.ok || response.status === 404);
      if (!removed) {
        throw new Error(message || 'Could not delete this fabric');
      }
      deletedIdsRef.current.add(fabric.id);
      deletingIdRef.current = null;
      setDeleteCard({ fabric, phase: 'deleted' });
    } catch (error) {
      deletingIdRef.current = null;
      setFabrics((prev) => (prev.some((item) => item.id === fabric.id) ? prev : [fabric, ...prev]));
      setDeleteCard({
        fabric,
        phase: 'error',
        message: error instanceof Error ? error.message : 'Could not delete this fabric',
      });
    }
  };

  const handleExportFabric = async (fabricId: string, sourceType?: string) => {
    try {
      const endpoint =
        sourceType === 'codebase'
          ? `api/v1/knowledge/${fabricId}/migration-export`
          : `api/v1/knowledge/${fabricId}/export`;
      const response = await authenticatedFetch(getApiUrl(endpoint));

      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        throw new Error(errText || `Export failed (${response.status})`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download =
        sourceType === 'codebase'
          ? `fabric_${fabricId}_migration.json`
          : `fabric_${fabricId}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error exporting fabric:', error);
      alert(error instanceof Error ? error.message : 'Export failed');
    }
  };

  const handleReanalyzeCodebase = async (fabricId: string) => {
    if (!window.confirm('Re-analyze this codebase fabric?')) return;
    try {
      const form = new FormData();
      const response = await fetch(getApiUrl(`api/v1/knowledge/${fabricId}/codebase/reanalyze`), {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: form,
      });
      const payload = await response.json();
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.detail || payload?.message || 'Re-analyze failed');
      }
      alert('Re-analysis started. Refresh this page in a minute.');
      handleRefresh();
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : 'Re-analyze failed');
    }
  };

  const handleValidateFabric = async (fabricId: string, fabricName: string) => {
    try {
      const response = await authenticatedFetch(getApiUrl(`api/v1/knowledge/validate-knowledge/${fabricId}`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          questions: [
            "What is this document about?",
            "What are the key points discussed?",
            "What is the main purpose?"
          ]
        }),
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          const data = result.data;
          alert(`✅ Knowledge Validation Results for ${fabricName}:\n\n` +
                `📊 Validation Score: ${(data.validation_score * 100).toFixed(1)}%\n` +
                `🎯 Assessment: ${data.overall_assessment}\n` +
                `❓ Questions Tested: ${data.test_questions}\n\n` +
                `📝 Sample Response:\n"${data.results[0].response}"`);
        } else {
          alert(`❌ Validation failed: ${result.message}`);
        }
      } else {
        alert('❌ Failed to validate knowledge fabric');
      }
    } catch (error) {
      console.error('Error validating fabric:', error);
      alert('❌ Error validating knowledge fabric');
    }
  };

  const handleUseFabric = (fabric: KnowledgeFabric) => {
    setSelectedFabricForEndpoints(fabric);
    setShowEndpointsDialog(true);
  };

  const handleRenameFabric = async (fabric: KnowledgeFabric) => {
    const current = fabric.name || '';
    const nextName = window.prompt('Enter new fabric name', current);
    if (nextName == null) return;
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === current) return;
    try {
      const response = await authenticatedFetch(getApiUrl(`api/v1/knowledge/${fabric.id}/rename`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      });
      const result = await response.json();
      if (!response.ok || !result?.success) {
        throw new Error(result?.error || result?.message || 'Rename failed');
      }
      setFabrics((prev) => prev.map((f) => (f.id === fabric.id ? { ...f, name: result.data?.name || trimmed } : f)));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error renaming fabric';
      alert(`❌ ${message}`);
    }
  };

  const visibleFabrics = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return fabrics.filter((fabric) => {
      if (statusFilter === 'active' && fabric.status !== 'active') return false;
      if (statusFilter === 'failed' && fabric.status !== 'failed' && fabric.status !== 'error') return false;
      if (statusFilter === 'building' && fabric.status !== 'building' && fabric.status !== 'training') return false;
      if (statusFilter === 'indexed' && fabric.model_status !== 'indexed' && fabric.model_status !== 'trained') return false;
      if (!needle) return true;
      const haystack = [
        fabric.name,
        fabric.description,
        fabric.source_type,
        fabric.id,
        fabricKindLabel(fabric.weave_domain),
        ...(fabric.tags || []),
      ].join(' ').toLowerCase();
      return haystack.includes(needle);
    });
  }, [fabrics, query, statusFilter]);

  const catalogStats = [
    { label: 'Fabrics', value: fabrics.length },
    { label: 'Active', value: fabrics.filter((f) => f.status === 'active').length },
    { label: 'Indexed', value: fabrics.filter((f) => f.model_status === 'trained' || f.model_status === 'indexed').length },
    { label: 'Documents', value: fabrics.reduce((sum, f) => sum + (f.document_count || 0), 0) },
    { label: 'Chunks', value: fabrics.reduce((sum, f) => sum + (f.total_chunks || 0), 0) },
  ];

  if (initialLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#5ec8f2] mx-auto"></div>
          <p className="mt-4 text-[#8b9cb0]">Loading knowledge fabrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-16 left-[8%] h-72 w-72 rounded-full bg-[#5ec8f2]/25 blur-3xl" />
        <div className="absolute top-40 right-[6%] h-80 w-80 rounded-full bg-[#9b8bd4]/25 blur-3xl" />
        <div className="absolute top-[28rem] left-[28%] h-72 w-72 rounded-full bg-[#3ecf9b]/20 blur-3xl" />
        <div className="absolute bottom-10 right-[22%] h-64 w-64 rounded-full bg-[#5ec8f2]/15 blur-3xl" />
      </div>
      <div className="relative">

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-[#8b9cb0]">Catalog</p>
          <h1 className="text-2xl font-semibold tracking-[-0.03em] text-[#e8edf4]">Knowledge fabrics</h1>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center rounded-full border border-[rgba(148,163,184,0.16)] bg-white/[0.04] px-3 py-1.5 text-[13px] font-medium text-[#cbd5e1] transition hover:bg-white/[0.08] hover:text-[#e8edf4] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ArrowPathIcon className={`mr-1.5 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing' : 'Refresh'}
        </button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl border border-white/15 bg-white/[0.05] px-4 py-2.5 text-[12px] text-[#8b9cb0] shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-2xl">
        {catalogStats.map((stat) => (
          <span key={stat.label} className="inline-flex items-baseline gap-1.5">
            <span className="text-[15px] font-semibold tabular-nums text-[#e8edf4]">{stat.value.toLocaleString()}</span>
            {stat.label}
          </span>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <label className="relative min-w-[14rem] flex-1">
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8b9cb0]" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search name, source, or tag"
            className="w-full rounded-full border border-white/15 bg-white/[0.05] py-2 pl-9 pr-3 text-[13px] text-[#e8edf4] shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] outline-none backdrop-blur-2xl placeholder:text-[#8b9cb0] focus:border-[rgba(94,200,242,0.45)]"
          />
        </label>
        {([
          ['all', 'All'],
          ['active', 'Active'],
          ['failed', 'Failed'],
          ['building', 'Building'],
          ['indexed', 'Indexed'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setStatusFilter(id)}
            className={`rounded-full px-3 py-1.5 text-[12px] font-medium transition ${
              statusFilter === id
                ? 'bg-[#f5f5f7] text-[#111113]'
                : 'border border-[rgba(148,163,184,0.16)] text-[#8b9cb0] hover:text-[#e8edf4]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleFabrics.map((fabric) => {
          const pipelineStages = fabric.pipeline?.stages;
          const stages = Array.isArray(pipelineStages) ? pipelineStages : [];
          const tags = fabric.tags || [];
          const indexLabel = fabric.model_status === 'trained' ? 'indexed' : fabric.model_status;
          const indexTone = indexLabel === 'failed'
            ? 'text-[#f08984]'
            : indexLabel === 'indexed'
              ? 'text-[#3ecf9b]'
              : indexLabel === 'indexing' || indexLabel === 'training'
                ? 'text-[#5ec8f2]'
                : 'text-[#8b9cb0]';
          const iconButton = 'flex h-7 w-7 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] text-[#8b9cb0] shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-md transition hover:bg-white/[0.12] hover:text-[#e8edf4]';
          return (
            <article
              key={fabric.id}
              className="relative flex flex-col overflow-hidden rounded-2xl border border-white/15 bg-white/[0.06] p-3.5 shadow-[0_10px_40px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.22)] backdrop-blur-2xl transition duration-300 hover:border-white/30 hover:bg-white/[0.09]"
            >
              <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent" />
              <div className="pointer-events-none absolute -right-6 -top-8 h-20 w-20 rounded-full bg-[#5ec8f2]/25 blur-2xl" />
              <div className="flex items-start gap-2.5">
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#5ec8f2]/12 text-[#5ec8f2]">
                  {getSourceTypeIcon(fabric.source_type)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="truncate text-[15px] font-semibold tracking-[-0.02em] text-[#e8edf4]" title={fabric.name}>
                      {fabric.name}
                    </h3>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${getStatusColor(fabric.status)}`}>
                      {fabric.status}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-[#8b9cb0]">
                    <span className="uppercase tracking-[0.12em]">{fabric.source_type}</span>
                    <span className="mx-1.5 text-white/20">·</span>
                    <span className="text-[#5ec8f2]">{fabricKindLabel(fabric.weave_domain)}</span>
                    {indexLabel && (
                      <>
                        <span className="mx-1.5 text-white/20">·</span>
                        <span className={indexTone}>{indexLabel}</span>
                      </>
                    )}
                  </p>
                </div>
              </div>

              <p className="mt-2 text-[12px] text-[#cbd5e1]" title={formatDate(fabric.created_at)}>
                <span className="text-[#e8edf4]">{(fabric.document_count || 0).toLocaleString()}</span> docs
                <span className="mx-1.5 text-white/20">·</span>
                <span className="text-[#e8edf4]">{(fabric.total_chunks || 0).toLocaleString()}</span> chunks
                <span className="mx-1.5 text-white/20">·</span>
                {formatDate(fabric.created_at)}
              </p>

              {fabric.description && (
                <p className="mt-1.5 line-clamp-1 text-[12px] text-[#8b9cb0]" title={fabric.description}>
                  {fabric.description}
                </p>
              )}

              <div className="mt-2 flex flex-wrap gap-1">
                <span className="rounded-full border border-[rgba(155,139,212,0.4)] bg-[rgba(155,139,212,0.14)] px-1.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#d7cff5]">
                  CKF ready
                </span>
                {tags.slice(0, 3).map((tag) => (
                  <span key={tag} className="rounded-full border border-[rgba(148,163,184,0.14)] px-1.5 py-0.5 text-[10px] text-[#cbd5e1]">
                    {tag}
                  </span>
                ))}
                {tags.length > 3 && (
                  <span className="rounded-full border border-[rgba(148,163,184,0.14)] px-1.5 py-0.5 text-[10px] text-[#8b9cb0]">
                    +{tags.length - 3}
                  </span>
                )}
                {fabric.ontology_project_id && (
                  <span className="rounded-full border border-[rgba(94,200,242,0.3)] px-1.5 py-0.5 text-[10px] text-[#5ec8f2]">Ontology</span>
                )}
                {fabric.approved_ontology_version_id && (
                  <span className="rounded-full border border-[rgba(62,207,155,0.3)] px-1.5 py-0.5 text-[10px] text-[#3ecf9b]">Graph approved</span>
                )}
                {(fabricJobs[fabric.id] || []).slice(0, 1).map((job) => (
                  <span key={job.id} className={`rounded-full border px-1.5 py-0.5 text-[10px] ${jobStatusColor(job.status)}`}>
                    {jobTypeLabel(job.job_type)}: {job.status}
                  </span>
                ))}
              </div>

              {stages.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {stages.map((stage) => (
                    <span
                      key={`${fabric.id}-${stage.name}`}
                      title={stage.status}
                      className={`rounded-full px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
                        stage.status === 'completed'
                          ? 'text-[#3ecf9b]'
                          : stage.status === 'failed'
                            ? 'text-[#f08984]'
                            : 'text-[#8b9cb0]'
                      }`}
                    >
                      {stage.name}
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-3 flex items-center gap-1 border-t border-white/[0.06] pt-2.5">
                <button type="button" onClick={() => handleViewFabric(fabric)} className={iconButton} title="View details">
                  <EyeIcon className="h-3.5 w-3.5" />
                </button>
                {fabric.source_type !== 'codebase' && (
                  <button type="button" onClick={() => handleExportFabric(fabric.id, fabric.source_type)} className={iconButton} title="Export">
                    <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                  </button>
                )}
                {fabric.source_type === 'codebase' && (
                  <button type="button" onClick={() => handleReanalyzeCodebase(fabric.id)} className={iconButton} title="Re-analyze codebase">
                    <ArrowPathIcon className="h-3.5 w-3.5" />
                  </button>
                )}
                <button type="button" onClick={() => handleValidateFabric(fabric.id, fabric.name)} className={iconButton} title="Validate knowledge">
                  <MagnifyingGlassIcon className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => handleRenameFabric(fabric)} className={iconButton} title="Rename">
                  <PencilSquareIcon className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteFabric(fabric)}
                  disabled={deleteCard?.phase === 'deleting'}
                  className={`${iconButton} hover:text-[#f08984] disabled:opacity-40`}
                  title="Delete"
                >
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
                {fabric.source_type === 'codebase' && (
                  <button
                    type="button"
                    onClick={() => handleExportFabric(fabric.id, fabric.source_type)}
                    className="rounded-full border border-[rgba(62,207,155,0.35)] px-2 py-1 text-[10px] font-medium text-[#9af0ca]"
                    title="Download migration JSON"
                  >
                    JSON
                  </button>
                )}
                <div className="ml-auto flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => navigate(`/fabrics/${fabric.id}/knowledge-graph`)}
                    className="rounded-full border border-white/15 bg-white/[0.06] px-2.5 py-1 text-[11px] font-medium text-[#cbd5e1] shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-md transition hover:bg-white/[0.12] hover:text-[#e8edf4]"
                  >
                    Graph
                  </button>
                  <button
                    type="button"
                    onClick={() => handleUseFabric(fabric)}
                    className="rounded-full bg-[#f5f5f7] px-2.5 py-1 text-[11px] font-medium text-[#111113] transition hover:bg-white"
                  >
                    Use
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {fabrics.length === 0 && (
        <div className="py-16 text-center">
          <h3 className="text-lg font-medium text-[#e8edf4]">No knowledge fabrics yet</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#8b9cb0]">
            Create one from a document, database, CSV, ServiceNow source, or codebase.
          </p>
          <button
            type="button"
            onClick={() => navigate('/knowledge')}
            className="mt-5 rounded-full bg-[#f5f5f7] px-4 py-2 text-[13px] font-medium text-[#111113]"
          >
            Create a fabric
          </button>
        </div>
      )}

      {fabrics.length > 0 && visibleFabrics.length === 0 && (
        <p className="py-10 text-center text-sm text-[#8b9cb0]">No fabrics match this search.</p>
      )}

      {/* Dialogs */}
      {deleteCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-md">
          <div className="kf-card-in relative w-full max-w-sm overflow-hidden rounded-[28px] border border-white/20 bg-white/[0.08] px-6 py-7 text-center shadow-[0_30px_90px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.28)] backdrop-blur-2xl">
            <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/80 to-transparent" />
            <div className="pointer-events-none absolute -top-16 left-1/2 h-36 w-36 -translate-x-1/2 rounded-full bg-[#5ec8f2]/30 blur-3xl" />
            <div className="relative">
              {deleteCard.phase === 'deleting' && (
                <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-[#f5f5f7]" />
              )}
              {deleteCard.phase === 'deleted' && (
                <div className="mx-auto mb-4 flex h-8 w-8 items-center justify-center rounded-full border border-[rgba(62,207,155,0.4)] bg-[rgba(62,207,155,0.16)] text-[#3ecf9b]">
                  <TrashIcon className="h-4 w-4" />
                </div>
              )}
              <p className="text-[11px] uppercase tracking-[0.22em] text-[#8b9cb0]">
                {deleteCard.phase === 'deleting' ? 'Deleting' : deleteCard.phase === 'deleted' ? 'Deleted' : 'Could not delete'}
              </p>
              <h2 className="mt-2 truncate text-[20px] font-semibold tracking-[-0.03em] text-[#e8edf4]">
                {deleteCard.fabric.name}
              </h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[#cbd5e1]">
                {deleteCard.phase === 'deleting'
                  ? 'Removing this fabric from the catalog, along with its index and stored documents.'
                  : deleteCard.phase === 'deleted'
                    ? 'This fabric has been removed.'
                    : deleteCard.message}
              </p>
              {deleteCard.phase === 'error' && (
                <button
                  type="button"
                  onClick={() => setDeleteCard(null)}
                  className="mt-5 rounded-full bg-[#f5f5f7] px-4 py-2 text-[13px] font-medium text-[#111113] transition hover:bg-white"
                >
                  Close
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {selectedFabricForEndpoints && (
        <FabricEndpointsDialog
          isOpen={showEndpointsDialog}
          onClose={() => {
            setShowEndpointsDialog(false);
            setSelectedFabricForEndpoints(null);
          }}
          fabricId={selectedFabricForEndpoints.id}
          fabricName={selectedFabricForEndpoints.name}
        />
      )}
      </div>
    </div>
  );
};

export default Fabrics; 