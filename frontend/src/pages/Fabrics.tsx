import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DocumentTextIcon,
  ServerIcon,
  CpuChipIcon,
  CheckCircleIcon,
  SparklesIcon,
  BeakerIcon,
  GlobeAltIcon,
  TrashIcon,
  EyeIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  CubeIcon,
  PencilSquareIcon,
} from '@heroicons/react/24/outline';
import FabricEndpointsDialog from '../components/FabricEndpointsDialog';
import { apiRequest, authenticatedFetch, getApiUrl } from '../utils/api';
import { jobStatusColor, jobTypeLabel, platformApi, PlatformJob } from '../utils/platformApi';

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
  ontology_project_id?: string | null;
  approved_ontology_version_id?: string | null;
}

const Fabrics: React.FC = () => {
  const navigate = useNavigate();
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showEndpointsDialog, setShowEndpointsDialog] = useState(false);
  const [selectedFabricForEndpoints, setSelectedFabricForEndpoints] = useState<KnowledgeFabric | null>(null);
  const [fabricJobs, setFabricJobs] = useState<Record<string, PlatformJob[]>>({});

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
          setFabrics(list);
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
      if (list) setFabrics(list);
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
      case 'training':
        return 'border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.14)] text-[#5ec8f2]';
      case 'error':
        return 'border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.14)] text-[#f08984]';
      default:
        return 'border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#8b9cb0]';
    }
  };

  const getModelStatusColor = (status?: string) => {
    switch (status) {
      case 'trained':
        return 'border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b]';
      case 'training':
        return 'border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.14)] text-[#5ec8f2]';
      case 'failed':
        return 'border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.14)] text-[#f08984]';
      default:
        return 'border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#8b9cb0]';
    }
  };

  const getSourceTypeIcon = (sourceType: string) => {
    switch (sourceType) {
      case 'pdf':
        return <DocumentTextIcon className="h-5 w-5" />;
      case 'database':
        return <ServerIcon className="h-5 w-5" />;
      case 'mixed':
        return <BeakerIcon className="h-5 w-5" />;
      default:
        return <GlobeAltIcon className="h-5 w-5" />;
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
    // View fabric details - can be implemented later
    console.log('View fabric:', fabric);
  };

  const handleDeleteFabric = async (fabricId: string) => {
    if (window.confirm('Are you sure you want to delete this knowledge fabric?')) {
      try {
        // API call to delete fabric
        const response = await authenticatedFetch(getApiUrl(`api/v1/knowledge/${fabricId}`), {
          method: 'DELETE'
        });
        
        if (response.ok) {
          setFabrics(prev => prev.filter(f => f.id !== fabricId));
        }
      } catch (error) {
        console.error('Error deleting fabric:', error);
      }
    }
  };

  const handleExportFabric = async (fabricId: string) => {
    try {
      // API call to export fabric
      const response = await authenticatedFetch(getApiUrl(`api/v1/knowledge/${fabricId}/export`));
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `fabric_${fabricId}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Error exporting fabric:', error);
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(130deg,rgba(255,255,255,0.02),transparent_52%)]" />
        <div className="absolute -top-32 left-1/4 h-72 w-72 rounded-full bg-[#5ec8f2]/10 blur-3xl" />
        <div className="absolute top-1/3 -right-24 h-80 w-80 rounded-full bg-[#9b8bd4]/10 blur-3xl" />
        <div className="absolute -bottom-28 left-1/3 h-72 w-72 rounded-full bg-[#3ecf9b]/10 blur-3xl" />
      </div>

      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex items-center justify-center mb-4">
          <div className="p-3 rounded-full bg-[#10141d]/80 backdrop-blur-xl border border-[rgba(148,163,184,0.11)] shadow-lg shadow-black/30">
            <SparklesIcon className="h-8 w-8 text-[#5ec8f2]" />
          </div>
        </div>
        <p className="mb-3 text-[10px] uppercase tracking-[0.2em] text-[#8b9cb0]">Knowledge Operations</p>
        <h1 className="text-4xl font-semibold text-[#e8edf4] mb-4">
          Available Knowledge Fabrics
        </h1>
        <p className="text-base text-[#cbd5e1] max-w-3xl mx-auto mb-6">
          Manage and explore your created knowledge fabrics
        </p>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center rounded-xl border border-[rgba(148,163,184,0.11)] bg-white/[0.03] px-4 py-2 text-sm font-medium text-[#cbd5e1] backdrop-blur-xl transition-all hover:border-[rgba(148,163,184,0.2)] hover:bg-white/[0.05] hover:text-[#e8edf4] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ArrowPathIcon className={`mr-2 h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 mb-8 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-4 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div className="flex items-center">
            <div className="rounded-xl bg-[#5ec8f2]/15 p-2.5">
              <SparklesIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">Total Fabrics</p>
              <p className="text-xl font-semibold text-[#e8edf4]">{fabrics.length}</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-4 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div className="flex items-center">
            <div className="rounded-xl bg-[#3ecf9b]/15 p-2.5">
              <CheckCircleIcon className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">Active</p>
              <p className="text-xl font-semibold text-[#e8edf4]">
                {fabrics.filter(f => f.status === 'active').length}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-4 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div className="flex items-center">
            <div className="rounded-xl bg-[#9b8bd4]/15 p-2.5">
              <CpuChipIcon className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">Trained Models</p>
              <p className="text-xl font-semibold text-[#e8edf4]">
                {fabrics.filter(f => f.model_status === 'trained').length}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-4 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div className="flex items-center">
            <div className="rounded-xl bg-[#e8b84a]/15 p-2.5">
              <DocumentTextIcon className="h-6 w-6 text-orange-600" />
            </div>
            <div className="ml-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">Total Documents</p>
              <p className="text-xl font-semibold text-[#e8edf4]">
                {fabrics.reduce((sum, f) => sum + f.document_count, 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-4 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div className="flex items-center">
            <div className="rounded-xl bg-[#5ec8f2]/15 p-2.5">
              <CubeIcon className="h-6 w-6 text-teal-600" />
            </div>
            <div className="ml-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">Total Chunks</p>
              <p className="text-xl font-semibold text-[#e8edf4]">
                {fabrics.reduce((sum, f) => sum + (f.total_chunks || 0), 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Fabrics Grid */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {fabrics.map((fabric) => (
          <div
            key={fabric.id}
            className="group rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] transition-all duration-300 hover:border-[rgba(148,163,184,0.2)] hover:-translate-y-0.5"
          >
            <div className="p-5">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="rounded-lg bg-[#5ec8f2]/15 p-2">
                    {getSourceTypeIcon(fabric.source_type)}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-[#e8edf4]">
                      {fabric.name}
                    </h3>
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">
                      {fabric.source_type.toUpperCase()}
                    </p>
                  </div>
                </div>
                <span className={`px-3 py-1 text-xs font-medium rounded-full ${getStatusColor(fabric.status)}`}>
                  {fabric.status}
                </span>
              </div>

              {/* Description */}
              {fabric.description && (
                <p className="text-[#cbd5e1] mb-4 line-clamp-2">
                  {fabric.description}
                </p>
              )}

              {/* Tags */}
              {fabric.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {fabric.tags.slice(0, 3).map((tag, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 border border-[rgba(148,163,184,0.11)] bg-white/[0.04] text-[#cbd5e1] text-xs rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                  {fabric.tags.length > 3 && (
                    <span className="px-2 py-1 border border-[rgba(148,163,184,0.11)] bg-white/[0.04] text-[#cbd5e1] text-xs rounded-full">
                      +{fabric.tags.length - 3} more
                    </span>
                  )}
                </div>
              )}

              {/* Platform status */}
              <div className="mb-4 flex flex-wrap gap-2">
                {fabric.ontology_project_id && (
                  <span className="rounded-full border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.1)] px-2 py-0.5 text-[10px] text-[#5ec8f2]">
                    Ontology linked
                  </span>
                )}
                {fabric.approved_ontology_version_id && (
                  <span className="rounded-full border border-[rgba(62,207,155,0.3)] bg-[rgba(62,207,155,0.1)] px-2 py-0.5 text-[10px] text-[#3ecf9b]">
                    Graph approved
                  </span>
                )}
                {(fabricJobs[fabric.id] || []).slice(0, 1).map((job) => (
                  <span
                    key={job.id}
                    className={`rounded-full border px-2 py-0.5 text-[10px] ${jobStatusColor(job.status)}`}
                  >
                    {jobTypeLabel(job.job_type)}: {job.status}
                  </span>
                ))}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 mb-4 rounded-xl border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-[#8b9cb0]">Documents</p>
                  <p className="text-lg font-semibold text-[#e8edf4]">
                    {fabric.document_count.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-[#8b9cb0]">Chunks</p>
                  <p className="text-lg font-semibold text-[#e8edf4]">
                    {fabric.total_chunks?.toLocaleString() || '0'}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-[#8b9cb0]">Created</p>
                  <p className="text-sm font-medium text-[#e8edf4]">
                    {formatDate(fabric.created_at)}
                  </p>
                </div>
              </div>

              {/* Status */}
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs uppercase tracking-[0.16em] text-[#8b9cb0]">Model Status</span>
                {fabric.model_status && (
                  <span className={`px-3 py-1 text-xs font-medium rounded-full ${getModelStatusColor(fabric.model_status)}`}>
                    {fabric.model_status}
                  </span>
                )}
              </div>

              {/* Action Buttons - all controls stay inside widget */}
              <div className="space-y-2 rounded-xl border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-3">
                <div className="grid grid-cols-5 gap-2">
                  <button
                    onClick={() => handleViewFabric(fabric)}
                    className="flex items-center justify-center rounded-lg border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-2 text-[#8b9cb0] transition-colors hover:border-[rgba(94,200,242,0.35)] hover:text-[#5ec8f2]"
                    title="View Details"
                  >
                    <EyeIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleExportFabric(fabric.id)}
                    className="flex items-center justify-center rounded-lg border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-2 text-[#8b9cb0] transition-colors hover:border-[rgba(62,207,155,0.35)] hover:text-[#3ecf9b]"
                    title="Export"
                  >
                    <ArrowDownTrayIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleValidateFabric(fabric.id, fabric.name)}
                    className="flex items-center justify-center rounded-lg border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-2 text-[#8b9cb0] transition-colors hover:border-[rgba(155,139,212,0.35)] hover:text-[#9b8bd4]"
                    title="Validate Knowledge"
                  >
                    <MagnifyingGlassIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleRenameFabric(fabric)}
                    className="flex items-center justify-center rounded-lg border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-2 text-[#8b9cb0] transition-colors hover:border-[rgba(94,200,242,0.35)] hover:text-[#5ec8f2]"
                    title="Rename"
                  >
                    <PencilSquareIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteFabric(fabric.id)}
                    className="flex items-center justify-center rounded-lg border border-[rgba(148,163,184,0.11)] bg-white/[0.03] p-2 text-[#8b9cb0] transition-colors hover:border-[rgba(240,137,132,0.35)] hover:text-[#f08984]"
                    title="Delete"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>

                <button
                  onClick={() => navigate(`/fabrics/${fabric.id}/knowledge-graph`)}
                  className="w-full rounded-lg border border-[rgba(148,163,184,0.11)] bg-white/[0.03] py-2 px-4 text-sm font-medium text-[#cbd5e1] transition-colors hover:border-[rgba(148,163,184,0.2)] hover:bg-white/[0.05] hover:text-[#e8edf4]"
                >
                  View Knowledge Graph
                </button>
                <button
                  onClick={() => handleUseFabric(fabric)}
                  className="w-full rounded-lg border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30 py-2 px-4 text-sm font-medium text-[#e8edf4] transition-all duration-200 hover:from-[#5ec8f2]/40 hover:to-[#9b8bd4]/40"
                >
                  Use Fabric
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {fabrics.length === 0 && (
        <div className="text-center py-12">
          <div className="mx-auto w-24 h-24 rounded-full border border-[rgba(148,163,184,0.11)] bg-white/[0.03] flex items-center justify-center mb-6">
            <SparklesIcon className="h-12 w-12 text-[#5ec8f2]" />
          </div>
          <h3 className="text-lg font-medium text-[#e8edf4] mb-2">No Knowledge Fabrics Yet</h3>
          <p className="text-[#cbd5e1] mb-6">
            Create your first knowledge fabric by uploading documents or connecting to databases.
          </p>
          <button className="rounded-lg border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30 px-6 py-3 font-medium text-[#e8edf4] hover:from-[#5ec8f2]/40 hover:to-[#9b8bd4]/40 transition-colors">
            Create Knowledge Fabric
          </button>
        </div>
      )}

      {/* Dialogs */}
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
  );
};

export default Fabrics; 