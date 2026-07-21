import React, { useEffect, useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  AdjustmentsHorizontalIcon,
  BeakerIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  SparklesIcon,
  ArrowPathIcon,
  CpuChipIcon,
  MagnifyingGlassCircleIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline';
import { ComponentType } from 'react';
import { ontologyApi, EnrichmentCandidate, OntologyVersionRecord, OntologyProject } from '../../utils/ontologyApi';
import { getWeaveDomain, isPharmaManufacturing } from '../../utils/weaveDomain';

const modeHelp: Record<string, string> = {
  manual: 'Manual: detect only; every change requires steward action.',
  assisted: 'Assisted: AI suggests, steward approval required before promotion.',
  controlled_auto_apply: 'Controlled Auto-Apply: low-risk additive changes may auto-apply by policy.',
};

type MetricCard = {
  label: string;
  value: string;
  Icon: ComponentType<{ className?: string }>;
};

const OntologyEnrichment: React.FC = () => {
  const [candidates, setCandidates] = useState<EnrichmentCandidate[]>([]);
  const [versions, setVersions] = useState<OntologyVersionRecord[]>([]);
  const [governanceMode, setGovernanceMode] = useState<'manual' | 'assisted' | 'controlled_auto_apply'>('assisted');
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [policyLogs, setPolicyLogs] = useState<Array<Record<string, unknown>>>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [changeTypeFilter, setChangeTypeFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [sensitivityFilter, setSensitivityFilter] = useState<string>('all');
  const [datasetFilter, setDatasetFilter] = useState<string>('');
  const [minConfidence, setMinConfidence] = useState<number>(0);
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [fromVersionId, setFromVersionId] = useState<string>('');
  const [toVersionId, setToVersionId] = useState<string>('');
  const [compareResult, setCompareResult] = useState<Record<string, unknown> | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);
  const timelineDefaultsApplied = useRef(false);
  const [showDiscoveryFx, setShowDiscoveryFx] = useState(false);
  const [fxStage, setFxStage] = useState(0);
  const [fxProgress, setFxProgress] = useState(0);
  const [sourceMode, setSourceMode] = useState<'demo' | 'project'>('demo');
  const [projects, setProjects] = useState<OntologyProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [projectVersions, setProjectVersions] = useState<Array<{ id: string; version_label: string; is_draft: boolean }>>([]);
  const [selectedProjectVersionId, setSelectedProjectVersionId] = useState<string>('');

  const weaveDomain = getWeaveDomain();
  const selected = useMemo(() => candidates.find(c => c.id === selectedId) || null, [candidates, selectedId]);
  const filteredCandidates = useMemo(() => {
    return candidates.filter(c => {
      if (statusFilter !== 'all' && c.status !== statusFilter) return false;
      if (changeTypeFilter !== 'all' && c.changeType !== changeTypeFilter) return false;
      if (riskFilter !== 'all' && c.riskLevel !== riskFilter) return false;
      if (sensitivityFilter !== 'all' && c.sensitivity !== sensitivityFilter) return false;
      if (datasetFilter.trim() && !c.sourceDatasetId.toLowerCase().includes(datasetFilter.trim().toLowerCase())) return false;
      if (Math.round(c.confidenceScore * 100) < minConfidence) return false;
      return true;
    });
  }, [candidates, statusFilter, changeTypeFilter, riskFilter, sensitivityFilter, datasetFilter, minConfidence]);
  const uniqueStatuses = useMemo(
    () => candidates.map(c => c.status).filter((v, i, arr) => arr.indexOf(v) === i),
    [candidates]
  );
  const uniqueChangeTypes = useMemo(
    () => candidates.map(c => c.changeType).filter((v, i, arr) => arr.indexOf(v) === i),
    [candidates]
  );
  const uniqueRiskLevels = useMemo(
    () => candidates.map(c => c.riskLevel).filter((v, i, arr) => arr.indexOf(v) === i),
    [candidates]
  );
  const uniqueSensitivityLevels = useMemo(
    () => candidates.map(c => c.sensitivity).filter((v, i, arr) => arr.indexOf(v) === i),
    [candidates]
  );
  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / pageSize));
  const pagedCandidates = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredCandidates.slice(start, start + pageSize);
  }, [filteredCandidates, page]);

  const loadAll = async () => {
    setLoading(true);
    try {
      await Promise.all([
        ontologyApi.listCandidates().then(setCandidates).catch(() => setCandidates([])),
        ontologyApi.listOntologyVersions().then(setVersions).catch(() => setVersions([])),
        ontologyApi.getGovernanceMode().then(data => setGovernanceMode(data.mode as 'manual' | 'assisted' | 'controlled_auto_apply')).catch(() => {}),
        ontologyApi.listProjects().then((data) => {
          setProjects(data);
          setSelectedProjectId((prev) => (prev || (data.length > 0 ? data[0].id : '')));
        }).catch(() => setProjects([])),
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedProjectId) {
      setProjectVersions([]);
      return;
    }
    ontologyApi.listVersions(selectedProjectId).then((data) => {
      setProjectVersions(data);
      if (data.length > 0) setSelectedProjectVersionId(data[0].id);
    }).catch(() => setProjectVersions([]));
  }, [selectedProjectId]);

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, changeTypeFilter, riskFilter, sensitivityFilter, datasetFilter, minConfidence]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  useEffect(() => {
    if (timelineDefaultsApplied.current || versions.length < 2) return;
    const newest = versions[0];
    const oldest = versions[versions.length - 1];
    setFromVersionId(oldest.id);
    setToVersionId(newest.id);
    timelineDefaultsApplied.current = true;
  }, [versions]);

  const formatVersionDate = (iso?: string) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  };

  const handleCompareVersions = async () => {
    if (!fromVersionId || !toVersionId) {
      toast.error('Select both a “from” and “to” ontology version.');
      return;
    }
    if (fromVersionId === toVersionId) {
      toast.error('Choose two different versions to compare.');
      return;
    }
    setCompareLoading(true);
    setCompareResult(null);
    try {
      const data = await ontologyApi.compareOntologyVersions(fromVersionId, toVersionId);
      setCompareResult(data as Record<string, unknown>);
      const summary = data && typeof data === 'object' && 'summary' in data ? (data as { summary?: Record<string, number> }).summary : undefined;
      if (summary) {
        toast.success(
          `Diff: +${summary.attributes_added ?? 0}/−${summary.attributes_removed ?? 0} attributes, +${summary.entities_added ?? 0}/−${summary.entities_removed ?? 0} entities`
        );
      } else {
        toast.success('Comparison complete.');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Compare failed';
      toast.error(msg);
    } finally {
      setCompareLoading(false);
    }
  };

  const handleRollbackVersion = async (versionId: string, label: string) => {
    if (!window.confirm(`Create a rollback snapshot from version ${label}? The ontology snapshot will be restored to this point.`)) return;
    setRollingBackId(versionId);
    try {
      await ontologyApi.rollbackOntologyVersion(versionId, 'admin', `Rollback from enrichment timeline (${label})`);
      toast.success('Rollback version recorded.');
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Rollback failed');
    } finally {
      setRollingBackId(null);
    }
  };

  const refreshCandidate = (candidateId: string) => {
    ontologyApi.getCandidate(candidateId).then(data => {
      setPolicyLogs(data.policy_logs || []);
      setCandidates(prev => prev.map(c => (c.id === candidateId ? data.candidate : c)));
    });
  };

  const updateMode = async (mode: 'manual' | 'assisted' | 'controlled_auto_apply') => {
    await ontologyApi.updateGovernanceMode(mode, 'admin');
    setGovernanceMode(mode);
  };

  const summary = useMemo(() => {
    const pending = candidates.filter(c => c.status === 'pending_approval').length;
    const autoApplied = candidates.filter(c => c.status === 'auto_applied').length;
    const highRisk = candidates.filter(c => c.riskLevel === 'high').length;
    const sensitive = candidates.filter(c => c.sensitivity !== 'non_sensitive').length;
    return { total: candidates.length, pending, autoApplied, highRisk, sensitive };
  }, [candidates]);

  const runDemoDiscovery = async () => {
    if (sourceMode === 'project' && !selectedProjectId) {
      window.alert('Please select an ontology project for enrichment source.');
      return;
    }
    const demoFields = [
      { name: 'member_id', type: 'string', sample_values: ['M1204', 'M1205'] },
      { name: 'subscriber_id', type: 'string', sample_values: ['S1204', 'S1205'] },
      { name: 'care_gap_priority_score', type: 'number', sample_values: [0.72, 0.19] },
      { name: 'diagnosis_cluster', type: 'string', sample_values: ['Cardio', 'Pulmonary'] },
      { name: 'provider_risk_tier', type: 'string', sample_values: ['T1', 'T2'] },
    ];
    setLoading(true);
    setShowDiscoveryFx(true);
    setFxStage(0);
    setFxProgress(4);
    const stageTimers: number[] = [];
    const progressTimer = window.setInterval(() => {
      setFxProgress(p => Math.min(96, p + Math.random() * 9));
    }, 180);
    stageTimers.push(window.setTimeout(() => setFxStage(1), 700));
    stageTimers.push(window.setTimeout(() => setFxStage(2), 1500));
    stageTimers.push(window.setTimeout(() => setFxStage(3), 2400));
    stageTimers.push(window.setTimeout(() => setFxStage(4), 3300));
    const minimumAnimationTime = new Promise<void>((resolve) => {
      stageTimers.push(window.setTimeout(() => resolve(), 3800));
    });
    try {
      const runPromise = sourceMode === 'project'
        ? ontologyApi.discoverEnrichmentFromProject({
            project_id: selectedProjectId,
            version_id: selectedProjectVersionId || undefined,
            created_by: 'system',
          })
        : ontologyApi.discoverEnrichment({
            source_dataset_id: 'demo_member_claim_feed',
            fields: demoFields,
            metadata: { origin: 'demo', purpose: 'enrichment' },
            created_by: 'system',
          });
      await Promise.all([runPromise, minimumAnimationTime]);
      setFxProgress(100);
      setFxStage(5);
      await new Promise(resolve => window.setTimeout(resolve, 450));
    } finally {
      window.clearInterval(progressTimer);
      stageTimers.forEach(t => window.clearTimeout(t));
      setShowDiscoveryFx(false);
      setFxProgress(0);
      setFxStage(0);
      await loadAll();
    }
  };

  const discoveryStages = [
    { label: 'Ingesting source schema', Icon: BeakerIcon },
    { label: 'Profiling fields and values', Icon: MagnifyingGlassCircleIcon },
    { label: 'Computing ontology similarity', Icon: CpuChipIcon },
    { label: 'Running policy and risk checks', Icon: ShieldExclamationIcon },
    { label: 'Generating enrichment candidates', Icon: SparklesIcon },
    { label: 'Discovery complete', Icon: CheckCircleIcon },
  ];

  const metricCards: MetricCard[] = [
    { label: 'Total discovered', value: String(summary.total), Icon: SparklesIcon },
    { label: 'Pending approvals', value: String(summary.pending), Icon: ExclamationTriangleIcon },
    { label: 'Auto-applied', value: String(summary.autoApplied), Icon: CheckCircleIcon },
    { label: 'High risk', value: String(summary.highRisk), Icon: ShieldCheckIcon },
    { label: 'Sensitive', value: String(summary.sensitive), Icon: AdjustmentsHorizontalIcon },
  ];
  const riskBadgeClass = (risk: string) =>
    risk === 'high'
      ? 'border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.14)] text-[#f08984]'
      : risk === 'medium'
        ? 'border-[rgba(251,191,36,0.35)] bg-[rgba(251,191,36,0.14)] text-[#facc15]'
        : 'border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b]';
  const confidencePct = selected ? Math.round((selected.confidenceScore || 0) * 100) : 0;
  const lineageEntries = selected ? Object.entries(selected.lineage || {}) : [];
  const policyEntries = policyLogs.map((entry, idx) => {
    const decision = String(entry.decision || 'unknown');
    const reason = String(entry.reason || 'No reason provided');
    const rule = String(entry.policyRule || entry.policy_rule || `rule_${idx + 1}`);
    const timestamp = String(entry.timestamp || '');
    return { idx, decision, reason, rule, timestamp };
  });

  return (
    <div className="space-y-6 text-[#cbd5e1] relative">
      {showDiscoveryFx && (
        <div className="fixed inset-0 z-50 bg-[#040508]/80 backdrop-blur-md flex items-center justify-center px-4">
          <div className="w-full max-w-2xl rounded-2xl border border-[rgba(94,200,242,0.3)] bg-[#0a0f17]/95 p-6 shadow-[0_0_80px_rgba(94,200,242,0.15)]">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-12 h-12 rounded-full border-2 border-[rgba(94,200,242,0.45)] border-t-[#5ec8f2] animate-spin" />
                <SparklesIcon className="w-5 h-5 text-[#5ec8f2] absolute inset-0 m-auto" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[#e8edf4]">AI Ontology Discovery Running</h3>
                <p className="text-xs text-[#8b9cb0]">Analyzing schema drift, sensitivity, and governance readiness...</p>
              </div>
            </div>
            <div className="mt-5 w-full h-2 rounded-full bg-white/[0.06] overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[#5ec8f2] via-[#9b8bd4] to-[#3ecf9b] transition-all duration-200"
                style={{ width: `${fxProgress}%` }}
              />
            </div>
            <p className="text-xs text-[#8b9cb0] mt-1">{Math.round(fxProgress)}%</p>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {discoveryStages.map((stage, idx) => {
                const active = idx <= fxStage;
                const StageIcon = stage.Icon;
                return (
                  <div
                    key={stage.label}
                    className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-all ${
                      active
                        ? 'border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)] text-[#e8edf4]'
                        : 'border-[rgba(148,163,184,0.16)] bg-white/[0.02] text-[#8b9cb0]'
                    }`}
                  >
                    <StageIcon className={`w-4 h-4 ${active ? 'text-[#5ec8f2]' : 'text-[#8b9cb0]'}`} />
                    {stage.label}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[#e8edf4]">Ontology Enrichment Queue</h1>
          <p className="text-sm text-[#8b9cb0] mt-1">AI-assisted discovery, governance, and versioned promotion workflow.</p>
        </div>
        <button onClick={runDemoDiscovery} className="inline-flex items-center px-3 py-2 rounded-lg bg-[rgba(94,200,242,0.16)] border border-[rgba(94,200,242,0.3)] text-[#5ec8f2] text-sm">
          <BeakerIcon className="w-4 h-4 mr-2" />
          {sourceMode === 'project' ? 'Run project enrichment' : 'Run demo discovery'}
        </button>
      </div>

      <div className="rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div>
            <p className="text-xs text-[#8b9cb0] mb-1">Enrichment source</p>
            <select value={sourceMode} onChange={e => setSourceMode(e.target.value as 'demo' | 'project')} className="w-full rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-3 py-2 text-sm">
              <option value="demo">Demo dataset (sample fields)</option>
              <option value="project">Existing ontology project</option>
            </select>
          </div>
          <div>
            <p className="text-xs text-[#8b9cb0] mb-1">Project</p>
            <select disabled={sourceMode !== 'project'} value={selectedProjectId} onChange={e => setSelectedProjectId(e.target.value)} className="w-full rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-3 py-2 text-sm disabled:opacity-50">
              <option value="">Select project</option>
              {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <p className="text-xs text-[#8b9cb0] mb-1">Version</p>
            <select disabled={sourceMode !== 'project'} value={selectedProjectVersionId} onChange={e => setSelectedProjectVersionId(e.target.value)} className="w-full rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-3 py-2 text-sm disabled:opacity-50">
              <option value="">Latest</option>
              {projectVersions.map(v => <option key={v.id} value={v.id}>{v.version_label}{v.is_draft ? ' (draft)' : ''}</option>)}
            </select>
          </div>
        </div>
        <p className="text-xs text-[#8b9cb0] mt-2">
          Current source: {sourceMode === 'project'
            ? (selectedProjectId ? `Ontology Project (${projects.find(p => p.id === selectedProjectId)?.name || selectedProjectId})` : 'Ontology Project (not selected)')
            : 'Demo Dataset'}.
          Queue `Source` column reflects this origin.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {metricCards.map(({ label, value, Icon }) => (
          <div key={label} className="rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] px-4 py-3">
            <div className="flex items-center gap-2 text-[#8b9cb0] text-xs">
              <Icon className="w-4 h-4" />
              {label}
            </div>
            <div className="text-xl text-[#e8edf4] font-semibold mt-1">{value}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm text-[#e8edf4] font-semibold">Governance Mode</h2>
            <p className="text-xs text-[#8b9cb0] mt-0.5">{modeHelp[governanceMode]}</p>
          </div>
          <select
            value={governanceMode}
            onChange={e => updateMode(e.target.value as 'manual' | 'assisted' | 'controlled_auto_apply')}
            className="rounded-lg border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-3 py-2 text-sm"
          >
            <option value="manual">Manual</option>
            <option value="assisted">Assisted</option>
            <option value="controlled_auto_apply">Controlled Auto-Apply</option>
          </select>
        </div>
      </div>

      {isPharmaManufacturing(weaveDomain) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-xl border border-[rgba(155,139,212,0.32)] bg-[rgba(155,139,212,0.08)] p-4">
            <h2 className="text-sm font-semibold text-[#e8edf4] mb-2">Pharma enrichment capabilities</h2>
            <p className="text-xs text-[#8b9cb0] mb-3">
              Promote approved discovery into the ontology with scientific operations—always behind governance. Regulated elements are never directly auto-updated.
            </p>
            <ul className="text-sm text-[#cbd5e1] list-disc pl-4 space-y-1.5">
              <li>Normalize scientific terms and map synonyms</li>
              <li>Standardize units and classify CPP / CQA</li>
              <li>Enrich batch lineage and experiment-to-outcome mapping</li>
              <li>Link SOPs and protocols; link deviations and CAPA</li>
              <li>Generate ontology version diff; route changes for approval</li>
            </ul>
          </div>
          <div className="rounded-xl border border-[rgba(240,137,132,0.25)] bg-[rgba(240,137,132,0.06)] p-4">
            <h2 className="text-sm font-semibold text-[#e8edf4] mb-2">Governance & risk routing</h2>
            <ul className="text-xs text-[#cbd5e1] list-disc pl-4 space-y-2">
              <li>
                <strong className="text-[#94a3b8]">Low-risk</strong> additive attributes may auto-apply only when governance mode and policy allow.
              </li>
              <li>
                <strong className="text-[#94a3b8]">Medium-risk</strong> changes require ontology steward approval before promotion.
              </li>
              <li>
                <strong className="text-[#94a3b8]">High-risk</strong> changes require QA approval.
              </li>
              <li>
                <strong className="text-[#94a3b8]">Regulatory interpretation</strong> requires regulatory reviewer approval.
              </li>
              <li className="text-[#f08984]">
                Approved process range changes must never auto-apply—always routed explicitly.
              </li>
            </ul>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] overflow-hidden">
          <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.16)] flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#e8edf4]">Enrichment Queue</h3>
            <button onClick={loadAll} className="text-xs text-[#5ec8f2] inline-flex items-center">
              <ArrowPathIcon className="w-3.5 h-3.5 mr-1" />
              Refresh
            </button>
          </div>
          <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.11)] grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs">
              <option value="all">All status</option>
              {uniqueStatuses.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            <select value={changeTypeFilter} onChange={e => setChangeTypeFilter(e.target.value)} className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs">
              <option value="all">All change types</option>
              {uniqueChangeTypes.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs">
              <option value="all">All risk</option>
              {uniqueRiskLevels.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            <select value={sensitivityFilter} onChange={e => setSensitivityFilter(e.target.value)} className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs">
              <option value="all">All sensitivity</option>
              {uniqueSensitivityLevels.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            <input value={datasetFilter} onChange={e => setDatasetFilter(e.target.value)} placeholder="Dataset filter" className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs" />
            <input type="number" min={0} max={100} value={minConfidence} onChange={e => setMinConfidence(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} placeholder="Min conf" className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs" />
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-white/[0.04] text-[#8b9cb0]">
                <tr>
                  {['ID', 'Source', 'Change', 'Entity', 'Sensitivity', 'Risk', 'Confidence', 'Status', 'Action'].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pagedCandidates.map(c => (
                  <tr key={c.id} className="border-t border-[rgba(148,163,184,0.11)] hover:bg-white/[0.03]">
                    <td className="px-3 py-2 font-mono text-xs">{c.id}</td>
                    <td className="px-3 py-2">{c.sourceDatasetId}</td>
                    <td className="px-3 py-2">{c.changeType}</td>
                    <td className="px-3 py-2">{c.suggestedEntity || '-'}</td>
                    <td className="px-3 py-2">{c.sensitivity}</td>
                    <td className="px-3 py-2">{c.riskLevel}</td>
                    <td className="px-3 py-2">{Math.round(c.confidenceScore * 100)}%</td>
                    <td className="px-3 py-2">{c.status}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => { setSelectedId(c.id); refreshCandidate(c.id); }} className="text-[#5ec8f2] text-xs">Open</button>
                    </td>
                  </tr>
                ))}
                {!loading && pagedCandidates.length === 0 && (
                  <tr><td colSpan={9} className="px-3 py-4 text-center text-[#8b9cb0]">No candidates yet. Run discovery to populate queue.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 border-t border-[rgba(148,163,184,0.11)] flex items-center justify-between text-xs text-[#8b9cb0]">
            <span>Showing {pagedCandidates.length} of {filteredCandidates.length} candidates</span>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="px-2 py-1 rounded border border-[rgba(148,163,184,0.2)] disabled:opacity-40">Prev</button>
              <span>Page {page} / {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} className="px-2 py-1 rounded border border-[rgba(148,163,184,0.2)] disabled:opacity-40">Next</button>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] p-4 space-y-3">
          <h3 className="text-sm font-semibold text-[#e8edf4]">Candidate Detail</h3>
          {!selected && <p className="text-xs text-[#8b9cb0]">Select a candidate from the queue.</p>}
          {selected && (
            <>
              <div className="rounded-xl border border-[rgba(94,200,242,0.28)] bg-[radial-gradient(circle_at_top_right,rgba(94,200,242,0.18),transparent_45%),rgba(8,12,19,0.9)] p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-[#8b9cb0]">Field placement</p>
                <p className="text-sm text-[#e8edf4] mt-1">{selected.suggestedEntity || 'Unknown'} . {selected.suggestedAttribute || selected.suggestedRelationship || 'N/A'}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className={`px-2 py-0.5 rounded-md text-[11px] border ${riskBadgeClass(selected.riskLevel)}`}>risk: {selected.riskLevel}</span>
                  <span className="px-2 py-0.5 rounded-md text-[11px] border border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.14)] text-[#d5cdf1]">
                    sensitivity: {selected.sensitivity}
                  </span>
                  <span className="px-2 py-0.5 rounded-md text-[11px] border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.14)] text-[#5ec8f2]">
                    confidence: {confidencePct}%
                  </span>
                </div>
              </div>
              <div>
                <div className="text-xs text-[#8b9cb0] uppercase tracking-[0.14em]">AI rationale</div>
                <p className="text-sm text-[#cbd5e1] mt-1">{selected.aiRationale}</p>
              </div>
              <div>
                <div className="text-xs text-[#8b9cb0] uppercase tracking-[0.14em]">Lineage context</div>
                {lineageEntries.length > 0 ? (
                  <div className="mt-2 space-y-1.5 max-h-36 overflow-auto pr-1">
                    {lineageEntries.map(([key, value]) => (
                      <div key={key} className="rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-2 py-1.5">
                        <p className="text-[11px] text-[#8b9cb0]">{key}</p>
                        <p className="text-xs text-[#e8edf4] break-words">{typeof value === 'string' ? value : JSON.stringify(value)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#8b9cb0] mt-1">No lineage metadata available.</p>
                )}
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                <button onClick={async () => { await ontologyApi.approveCandidate(selected.id, 'steward'); loadAll(); refreshCandidate(selected.id); }} className="px-2 py-1 text-xs rounded bg-[rgba(62,207,155,0.16)] border border-[rgba(62,207,155,0.3)] text-[#3ecf9b]">Approve</button>
                <button onClick={async () => { await ontologyApi.rejectCandidate(selected.id, 'steward'); loadAll(); refreshCandidate(selected.id); }} className="px-2 py-1 text-xs rounded bg-white/[0.04] border border-[rgba(148,163,184,0.2)]">Reject</button>
                <button onClick={async () => { await ontologyApi.requestCandidateEvidence(selected.id, 'steward', 'Need additional evidence snippets'); loadAll(); refreshCandidate(selected.id); }} className="px-2 py-1 text-xs rounded bg-white/[0.04] border border-[rgba(148,163,184,0.2)]">Request Evidence</button>
                <button onClick={async () => { await ontologyApi.promoteCandidate(selected.id, 'steward'); loadAll(); refreshCandidate(selected.id); }} className="px-2 py-1 text-xs rounded bg-[rgba(94,200,242,0.16)] border border-[rgba(94,200,242,0.3)] text-[#5ec8f2]">Promote</button>
              </div>
              <div>
                <div className="text-xs text-[#8b9cb0] mt-2 uppercase tracking-[0.14em]">Policy decision log</div>
                {policyEntries.length > 0 ? (
                  <div className="mt-2 space-y-2 max-h-36 overflow-auto pr-1">
                    {policyEntries.map((entry) => (
                      <div key={`${entry.rule}-${entry.idx}`} className="rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] p-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-[11px] text-[#8b9cb0]">{entry.rule}</p>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] border ${entry.decision.toLowerCase().includes('reject') ? 'border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.14)] text-[#f08984]' : 'border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b]'}`}>
                            {entry.decision}
                          </span>
                        </div>
                        <p className="text-xs text-[#cbd5e1] mt-1">{entry.reason}</p>
                        {entry.timestamp && <p className="text-[10px] text-[#8b9cb0] mt-1">{entry.timestamp}</p>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#8b9cb0] mt-1">No policy decisions recorded yet.</p>
                )}
                <details className="mt-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#070b12] p-2">
                  <summary className="cursor-pointer text-xs text-[#8b9cb0]">View raw candidate JSON</summary>
                  <pre className="text-[11px] mt-2 overflow-auto max-h-40 text-[#cbd5e1]">{JSON.stringify(selected, null, 2)}</pre>
                </details>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-[rgba(148,163,184,0.18)] bg-white/[0.03] overflow-hidden">
        <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.16)] flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-[#e8edf4]">Ontology Version Timeline</h3>
            <p className="text-xs text-[#8b9cb0] mt-0.5">
              Snapshot history from enrichment promotions and rollbacks. Compare two checkpoints or roll back to a prior snapshot.
            </p>
          </div>
          <button type="button" onClick={() => loadAll()} className="text-xs text-[#5ec8f2] inline-flex items-center shrink-0">
            <ArrowPathIcon className="w-3.5 h-3.5 mr-1" />
            Refresh timeline
          </button>
        </div>
        <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.11)] grid grid-cols-1 md:grid-cols-4 gap-2">
          <select value={fromVersionId} onChange={e => setFromVersionId(e.target.value)} className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs">
            <option value="">From version (older)</option>
            {versions.map(v => <option key={v.id} value={v.id}>{v.versionNumber} · {formatVersionDate(v.createdAt)}</option>)}
          </select>
          <select value={toVersionId} onChange={e => setToVersionId(e.target.value)} className="rounded border border-[rgba(148,163,184,0.22)] bg-[#10141d]/70 px-2 py-1 text-xs">
            <option value="">To version (newer)</option>
            {versions.map(v => <option key={v.id} value={v.id}>{v.versionNumber} · {formatVersionDate(v.createdAt)}</option>)}
          </select>
          <button
            type="button"
            disabled={compareLoading || !fromVersionId || !toVersionId || fromVersionId === toVersionId}
            onClick={handleCompareVersions}
            className="px-2 py-1 text-xs rounded border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.12)] text-[#5ec8f2] disabled:opacity-45 disabled:cursor-not-allowed"
          >
            {compareLoading ? 'Comparing…' : 'Compare versions'}
          </button>
          <button type="button" onClick={() => setCompareResult(null)} className="px-2 py-1 text-xs rounded border border-[rgba(148,163,184,0.2)]">
            Clear compare
          </button>
        </div>
        {compareResult ? (
          <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.11)] space-y-2">
            <>
              {compareResult.summary && typeof compareResult.summary === 'object' && (
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {Object.entries(compareResult.summary as Record<string, unknown>).map(([k, val]) => (
                    <span key={k} className="px-2 py-0.5 rounded-md border border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.12)] text-[#d5cdf1]">
                      {k.replace(/_/g, ' ')}: {String(val)}
                    </span>
                  ))}
                </div>
              )}
              <div className="text-xs text-[#8b9cb0]">Full diff (JSON)</div>
              <pre className="mt-1 text-[11px] bg-[#0b0f16] rounded p-2 overflow-auto max-h-48">{JSON.stringify(compareResult, null, 2)}</pre>
            </>
          </div>
        ) : null}
        <div className="px-2 py-2">
          {versions.length === 0 && !loading && (
            <div className="px-2 py-6 text-xs text-[#8b9cb0] text-center">
              No version snapshots yet. Promote an enrichment candidate, or open this page after building an ontology workspace to capture a baseline automatically.
            </div>
          )}
          <ul className="relative border-l border-[rgba(148,163,184,0.2)] ml-4 space-y-0">
            {versions.map((v, idx) => (
              <li key={v.id} className="pl-6 pb-4 pt-0 relative">
                <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full bg-[#5ec8f2] ring-4 ring-[#0a0f17]" aria-hidden />
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 rounded-lg border border-[rgba(148,163,184,0.14)] bg-[rgba(8,12,19,0.65)] px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="text-sm text-[#e8edf4] font-medium">
                      {v.versionNumber}
                      <span className="font-normal text-[#8b9cb0]"> · {v.environment}</span>
                      {idx === 0 && (
                        <span className="ml-2 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border border-[rgba(62,207,155,0.35)] text-[#3ecf9b]">
                          Latest
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-[#cbd5e1] mt-1">{v.changeSummary}</div>
                    <div className="text-[11px] text-[#8b9cb0] mt-1 font-mono">{v.id}</div>
                    <div className="text-[11px] text-[#8b9cb0] mt-0.5">{formatVersionDate(v.createdAt)}</div>
                  </div>
                  <button
                    type="button"
                    disabled={rollingBackId !== null}
                    onClick={() => handleRollbackVersion(v.id, v.versionNumber)}
                    className="shrink-0 px-2 py-1 text-xs rounded border border-[rgba(148,163,184,0.25)] bg-white/[0.04] hover:bg-white/[0.07] disabled:opacity-45"
                  >
                    {rollingBackId === v.id ? 'Rolling back…' : 'Rollback to snapshot'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default OntologyEnrichment;
