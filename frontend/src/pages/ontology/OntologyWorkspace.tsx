import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowLeftIcon,
  PlayIcon,
  DocumentTextIcon,
  CubeIcon,
  LinkIcon,
  TagIcon,
  DocumentMagnifyingGlassIcon,
  ArrowDownTrayIcon,
  CheckIcon,
  XMarkIcon,
  TrashIcon,
  ClockIcon,
  TableCellsIcon,
  ShareIcon,
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline';
import { ontologyApi, OntologyVersion, OntologyClass, OntologyRelationship, OntologyAttribute, DiscoveryRun } from '../../utils/ontologyApi';
import { platformApi } from '../../utils/platformApi';

type Tab = 'entities' | 'relationships' | 'attributes' | 'rules' | 'canonical' | 'graph';

function clampPercent(value: unknown): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

const DISCOVERY_STAGE_LABELS: Record<string, string> = {
  artifact_load: 'Reading the source',
  pdf_process: 'Reading documents',
  xml_process: 'Reading structure',
  semantic_chunk: 'Splitting sections',
  concept_extract: 'Finding concepts',
  ontology_classify: 'Classifying entities',
  relation_inference: 'Binding relationships',
  attribute_map: 'Mapping attributes',
  ontology_assemble: 'Assembling the ontology',
  ontology_validate: 'Validating',
  persist: 'Saving the draft',
};

function discoveryStageLabel(stage?: string): string {
  if (!stage) return '';
  return DISCOVERY_STAGE_LABELS[stage] || stage.replace(/_/g, ' ');
}

/** Compact entity connection overview as node pills with hints. */
function EntityConnectionsList({
  nodeTypes,
  edgeTypes,
  graphJsonSchema,
}: {
  nodeTypes: Record<string, unknown>[];
  edgeTypes: Record<string, unknown>[];
  graphJsonSchema?: { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string; label?: string }> };
}) {
  const idToLabel = React.useMemo(() => {
    const map: Record<string, string> = {};
    if (graphJsonSchema?.nodes?.length) {
      graphJsonSchema.nodes.forEach(n => {
        map[n.id] = n.label ?? n.id;
        map[n.id.trim().toLowerCase()] = n.label ?? n.id;
      });
      return map;
    }
    nodeTypes.forEach(n => {
      const id = String(n.type ?? n.label ?? '—');
      map[id] = String(n.label ?? n.type ?? id);
      map[id.trim().toLowerCase()] = map[id];
    });
    return map;
  }, [graphJsonSchema, nodeTypes]);

  const connections = React.useMemo(() => {
    if (graphJsonSchema?.edges?.length) {
      return graphJsonSchema.edges.map(e => ({
        from: e.from,
        to: e.to,
        fromKey: e.from?.trim().toLowerCase() ?? '',
        toKey: e.to?.trim().toLowerCase() ?? '',
        toLabel: idToLabel[e.to?.trim().toLowerCase()] ?? idToLabel[e.to ?? ''] ?? e.to,
      }));
    }
    return edgeTypes.map(e => {
      const from = String(e.source_type ?? e.from ?? '');
      const to = String(e.target_type ?? e.to ?? '');
      const fromKey = from.trim().toLowerCase();
      const toKey = to.trim().toLowerCase();
      return {
        from,
        to,
        fromKey,
        toKey,
        toLabel: idToLabel[toKey] ?? to,
      };
    });
  }, [graphJsonSchema, edgeTypes, idToLabel]);

  const nodesWithHints = React.useMemo(() => {
    // Determine the list of nodes we want to show pills for
    const baseNodes: Array<{ id: string; label: string }> = [];
    if (graphJsonSchema?.nodes?.length) {
      graphJsonSchema.nodes.forEach(n => {
        baseNodes.push({ id: n.id, label: n.label ?? n.id });
      });
    } else if (nodeTypes.length) {
      nodeTypes.forEach(n => {
        const id = String(n.type ?? n.label ?? '—');
        const label = idToLabel[id.trim().toLowerCase()] ?? String(n.label ?? n.type ?? id);
        baseNodes.push({ id, label });
      });
    } else {
      // Fallback: infer from connections
      const seen: Record<string, boolean> = {};
      connections.forEach(c => {
        if (c.fromKey && !seen[c.fromKey]) {
          const raw = c.from ?? '';
          seen[c.fromKey] = true;
          baseNodes.push({ id: raw, label: idToLabel[c.fromKey] ?? raw });
        }
        if (c.toKey && !seen[c.toKey]) {
          const raw = c.to ?? '';
          seen[c.toKey] = true;
          baseNodes.push({ id: raw, label: idToLabel[c.toKey] ?? raw });
        }
      });
    }

    // Map node id -> outgoing target labels
    const outgoing: Record<string, string[]> = {};
    connections.forEach(c => {
      if (!c.fromKey || !c.toLabel) return;
      if (!outgoing[c.fromKey]) outgoing[c.fromKey] = [];
      if (!outgoing[c.fromKey].includes(c.toLabel)) {
        outgoing[c.fromKey].push(c.toLabel);
      }
    });

    return baseNodes.map(n => {
      const key = n.id.trim().toLowerCase();
      const outs = outgoing[key] ?? [];
      return { ...n, outgoing: outs };
    });
  }, [graphJsonSchema, nodeTypes, idToLabel, connections]);

  if (nodesWithHints.length === 0) {
    return (
      <div className="rounded-2xl border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] px-5 py-8 text-center">
        <LinkIcon className="w-10 h-10 text-[#5ec8f2] mx-auto mb-2" />
        <p className="text-sm text-gray-500">No entity connections yet. Run discovery to see how entities connect.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] px-4 py-3">
      <div className="flex gap-3 overflow-x-auto py-1">
        {nodesWithHints.map((n) => {
          const initials = n.label.slice(0, 2).toUpperCase();
          const outgoingPreview = n.outgoing.slice(0, 3);
          const more = n.outgoing.length - outgoingPreview.length;
          const hint =
            n.outgoing.length === 0
              ? 'No outgoing connections yet'
              : `→ ${outgoingPreview.join(', ')}${more > 0 ? ` +${more} more` : ''}`;
          return (
            <div
              key={n.id}
              className="flex items-center gap-2 px-3 py-2 rounded-2xl bg-[#10141d]/80 shadow-sm border border-[rgba(148,163,184,0.2)] min-w-[180px] max-w-xs"
            >
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[rgba(94,200,242,0.2)] border border-[rgba(94,200,242,0.4)] text-[#e8edf4] text-xs font-bold flex-shrink-0">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-gray-900 truncate" title={n.label}>{n.label}</p>
                <p className="text-[11px] text-gray-500 truncate" title={hint}>{hint}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultPanelHeader({
  icon: Icon,
  title,
  subtitle,
  countLabel,
  tone = 'teal',
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
  countLabel: string;
  tone?: 'teal' | 'cyan' | 'violet' | 'emerald' | 'slate';
}) {
  const accent =
    tone === 'cyan'
      ? { chip: 'text-[#7ad4ff] border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)]', bar: 'from-[#5ec8f2] to-[#7ad4c0]' }
      : tone === 'violet'
        ? { chip: 'text-[#c4b8ef] border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.12)]', bar: 'from-[#9b8bd4] to-[#5ec8f2]' }
        : tone === 'emerald'
          ? { chip: 'text-[#7ee0b8] border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.12)]', bar: 'from-[#3ecf9b] to-[#5ec8f2]' }
          : tone === 'slate'
            ? { chip: 'text-[#8b9cb0] border-[rgba(148,163,184,0.28)] bg-white/[0.04]', bar: 'from-[#8b9cb0] to-[#5ec8f2]' }
            : { chip: 'text-[#7ad4ff] border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)]', bar: 'from-[#5ec8f2] to-[#3ecf9b]' };

  return (
    <div className="relative px-5 py-5 border-b border-[rgba(148,163,184,0.12)]">
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${accent.bar} opacity-70`} />
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`relative p-2.5 rounded-2xl border ${accent.chip}`}>
            <Icon className="w-5 h-5" />
            <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-[#5ec8f2]/90" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#8b9cb0] mb-0.5">Discovery result</p>
            <h3 className="text-lg font-semibold text-[#e8edf4] tracking-tight truncate">{title}</h3>
            <p className="text-xs text-[#8b9cb0] mt-0.5">{subtitle}</p>
          </div>
        </div>
        <span className={`shrink-0 text-xs font-semibold px-3 py-1.5 rounded-xl border ${accent.chip}`}>{countLabel}</span>
      </div>
      <div className="or-flow-line mt-4" />
    </div>
  );
}

function StatusChip({ status }: { status?: string }) {
  const s = (status || 'draft').toLowerCase();
  const cls =
    s === 'approved'
      ? 'border-[rgba(62,207,155,0.4)] bg-[rgba(62,207,155,0.14)] text-[#7ee0b8]'
      : s === 'rejected'
        ? 'border-[rgba(148,163,184,0.3)] bg-white/[0.04] text-[#8b9cb0]'
        : 'border-[rgba(245,186,94,0.35)] bg-[rgba(245,186,94,0.12)] text-[#f5ba5e]';
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-[0.12em] px-2 py-0.5 rounded-md border ${cls}`}>
      {status || 'draft'}
    </span>
  );
}

function ConfidenceMeter({ value, tone = 'cyan' }: { value: number; tone?: 'cyan' | 'mint' | 'lilac' }) {
  const pct = Math.max(0, Math.min(100, Math.round((Number.isFinite(value) ? value : 0) * (value <= 1 ? 100 : 1))));
  const fill =
    tone === 'mint'
      ? 'from-[#3ecf9b] to-[#7ad4c0]'
      : tone === 'lilac'
        ? 'from-[#9b8bd4] to-[#5ec8f2]'
        : 'from-[#5ec8f2] to-[#3ecf9b]';
  return (
    <div className="flex items-center gap-2 min-w-[5.5rem]">
      <div className="flex-1 h-1 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="or-mono text-[10px] text-[#8b9cb0] tabular-nums w-8 text-right">{pct}%</span>
    </div>
  );
}

const GRAPH_NODE_DESCRIPTIONS: Record<string, string> = {
  clinicaldocument: 'Top-level clinical record container that anchors the full document graph.',
  recordtarget: 'Connects the document context to the subject (patient/member) of record.',
  patientrole: 'Patient identity role node containing identifiers and contact/location context.',
  patient: 'Person node with demographic and clinical identity attributes.',
  author: 'Captures who authored or generated the clinical content.',
  custodian: 'Represents the organization responsible for maintaining the record.',
  encounter: 'Represents a care interaction, visit, or event context.',
  observation: 'Clinical finding/measurement statement extracted from source evidence.',
  performer: 'Actor responsible for performing a documented activity.',
  participant: 'Entity involved in the encounter, action, or observation.',
};

function getGraphNodeDescription(nodeName: string): string {
  const key = nodeName.replace(/[^a-z0-9]/gi, '').toLowerCase();
  return GRAPH_NODE_DESCRIPTIONS[key] ?? 'Graph node type representing a semantic entity in the ontology.';
}

const OntologyWorkspace: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [projectName, setProjectName] = useState<string>('');
  const [projectDescription, setProjectDescription] = useState<string>('');
  const [projectArtifactIds, setProjectArtifactIds] = useState<string[]>([]);
  const [fabricLinkOrigins, setFabricLinkOrigins] = useState<string[]>([]);
  const [linkedFabricId, setLinkedFabricId] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<Array<{ name: string; path: string }>>([]);
  const [selectedArtifactIds, setSelectedArtifactIds] = useState<string[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<DiscoveryRun | null>(null);
  const [versions, setVersions] = useState<Array<{ id: string; version_label: string; is_draft: boolean }>>([]);
  const [runsHistory, setRunsHistory] = useState<DiscoveryRun[]>([]);
  const [version, setVersion] = useState<OntologyVersion | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('entities');
  const [selectedElement, setSelectedElement] = useState<OntologyClass | OntologyRelationship | OntologyAttribute | null>(null);
  const [polling, setPolling] = useState(false);
  const [trackedJobId, setTrackedJobId] = useState<string | null>(null);
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressStage, setProgressStage] = useState('');
  const discoverLock = useRef(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingProject, setDeletingProject] = useState(false);
  const [canonicalData, setCanonicalData] = useState<Record<string, unknown> | null>(null);
  const [graphData, setGraphData] = useState<Record<string, unknown> | null>(null);
  const [loadingCanonical, setLoadingCanonical] = useState(false);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [activeGraphNode, setActiveGraphNode] = useState<string | null>(null);
  const [platformAction, setPlatformAction] = useState<string | null>(null);
  const [platformLoading, setPlatformLoading] = useState(false);

  const extractFabricId = (description?: string, artifactsList?: Array<{ metadata?: { fabric_id?: string } }>) => {
    const fromMeta = (artifactsList || [])
      .map((a) => a?.metadata?.fabric_id)
      .find((id) => typeof id === 'string' && id.startsWith('fabric_'));
    if (fromMeta) return fromMeta;
    const desc = description || '';
    const m = desc.match(/\(id:\s*(fabric_[A-Za-z0-9_\-]+)\s*,/i);
    return m?.[1] || null;
  };

  const loadProject = useCallback(() => {
    if (!projectId) return;
    ontologyApi.getProject(projectId).then(p => {
      setProjectName(p.name);
      setProjectDescription(p.description || '');
      const linkedArtifacts = Array.isArray(p.source_artifacts)
        ? p.source_artifacts.map((a) => a.file_name || a.file_path || a.id).filter(Boolean)
        : [];
      setProjectArtifactIds(linkedArtifacts);
      const origins = Array.isArray(p.source_artifacts)
        ? p.source_artifacts
            .map((a) => {
              const meta = (a as unknown as { metadata?: { linked_from?: string; fabric_id?: string } }).metadata;
              return meta?.linked_from;
            })
            .filter((v): v is string => Boolean(v))
        : [];
      setFabricLinkOrigins(Array.from(new Set(origins)));
      const fabricId = extractFabricId(
        p.description,
        (p.source_artifacts || []) as Array<{ metadata?: { fabric_id?: string } }>,
      );
      setLinkedFabricId(fabricId);
    }).catch(() => {});
  }, [projectId]);

  const loadArtifacts = useCallback(() => {
    ontologyApi.getAvailableArtifacts().then(setArtifacts).catch(() => setArtifacts([]));
  }, []);

  const loadVersions = useCallback(() => {
    if (!projectId) return;
    ontologyApi.listVersions(projectId).then((list) => {
      const sorted = [...list].sort((a, b) => {
        const ta = String((a as { created_at?: string }).created_at || '');
        const tb = String((b as { created_at?: string }).created_at || '');
        return tb.localeCompare(ta);
      });
      setVersions(sorted);
      // Prefer newest draft when nothing is selected yet (avoids sticking on a
      // stale Record/Dataset artifact-discovery version).
      setVersionId((current) => {
        if (current && sorted.some((v) => v.id === current)) return current;
        return sorted[0]?.id ?? null;
      });
    }).catch(() => setVersions([]));
  }, [projectId]);

  const loadRunsHistory = useCallback(() => {
    if (!projectId) return;
    ontologyApi.listRuns(projectId).then(setRunsHistory).catch(() => setRunsHistory([]));
  }, [projectId]);

  const loadVersion = useCallback((vid: string) => {
    if (!projectId) return;
    ontologyApi.getVersion(projectId, vid).then(v => {
      setVersion(v);
      setVersionId(vid);
    }).catch(() => setVersion(null));
  }, [projectId]);

  useEffect(() => {
    loadProject();
    loadArtifacts();
    loadVersions();
    loadRunsHistory();
  }, [loadProject, loadArtifacts, loadVersions, loadRunsHistory]);

  useEffect(() => {
    const job = new URLSearchParams(location.search).get('job');
    if (!job) return;
    setTrackedJobId(job);
    setPolling(true);
  }, [location.search]);

  useEffect(() => {
    const active = runsHistory.find((r) => r.status === 'queued' || r.status === 'running');
    if (!active) return;
    setRunId((current) => current || active.id);
    setRun(active);
    setPolling(true);
    setProgressPercent((current) => Math.max(current, clampPercent(active.progress_percent)));
    setProgressStage(discoveryStageLabel(active.current_stage));
  }, [runsHistory]);

  useEffect(() => {
    if (!projectId || (!runId && !trackedJobId)) return undefined;
    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      try {
        if (trackedJobId) {
          const job = await platformApi.getJob(trackedJobId);
          const result = (job.result || {}) as { run_id?: string; version_id?: string };
          if (result.run_id) setRunId((current) => current || result.run_id || null);
          if (job.status === 'failed') {
            const errMsg =
              (job.error_payload as { message?: string } | null | undefined)?.message || 'Discovery failed';
            setPlatformAction(errMsg);
            setPolling(false);
            setTrackedJobId(null);
            loadRunsHistory();
            return;
          }
          if (job.status !== 'ready' && job.status !== 'completed') {
            setProgressPercent((current) => Math.max(current, clampPercent(job.progress_percent)));
            setPolling(true);
          }
          if ((job.status === 'ready' || job.status === 'completed') && result.version_id) {
            setProgressPercent(100);
            setPolling(false);
            setTrackedJobId(null);
            loadVersions();
            loadRunsHistory();
            setVersionId(result.version_id);
            loadVersion(result.version_id);
            setPlatformAction('Schema discovery complete.');
            return;
          }
        }
        if (runId) {
          const currentRun = await ontologyApi.getRun(projectId, runId);
          if (stopped) return;
          setRun(currentRun);
          setProgressPercent(clampPercent(currentRun.progress_percent));
          setProgressStage(discoveryStageLabel(currentRun.current_stage));
          setRunsHistory((rows) => [currentRun, ...rows.filter((row) => row.id !== currentRun.id)]);
          if (currentRun.status === 'completed' && currentRun.result_version_id) {
            setProgressPercent(100);
            setPolling(false);
            setTrackedJobId(null);
            setVersionId(currentRun.result_version_id);
            loadVersions();
            loadVersion(currentRun.result_version_id);
            loadRunsHistory();
            return;
          }
          if (currentRun.status === 'failed') {
            setPolling(false);
            setTrackedJobId(null);
            loadRunsHistory();
          }
        }
      } catch {
        // Keep the last percent on screen if a poll misses.
      }
    };
    tick();
    const timer = window.setInterval(tick, 2000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [projectId, runId, trackedJobId, loadVersions, loadVersion, loadRunsHistory]);

  useEffect(() => {
    if (versionId && projectId) loadVersion(versionId);
  }, [versionId, projectId, loadVersion]);

  useEffect(() => {
    if (activeTab === 'canonical' && versionId) {
      setLoadingCanonical(true);
      ontologyApi.exportCanonical(versionId).then((data) => { setCanonicalData(data as Record<string, unknown>); setLoadingCanonical(false); }).catch(() => setLoadingCanonical(false));
    }
  }, [activeTab, versionId]);

  useEffect(() => {
    if (activeTab === 'graph' && versionId) {
      setLoadingGraph(true);
      setGraphData(null);
      ontologyApi.exportGraph(versionId).then((res: { data?: Record<string, unknown> }) => {
        const data = res?.data ?? res as Record<string, unknown>;
        setGraphData(data);
        setLoadingGraph(false);
      }).catch(() => setLoadingGraph(false));
    }
  }, [activeTab, versionId, version?.updated_at]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploading(true);
    try {
      await ontologyApi.uploadDocuments(Array.from(files));
      loadArtifacts();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDiscover = async () => {
    if (!projectId || selectedArtifactIds.length === 0) return;
    if (discoverLock.current || polling) return;
    discoverLock.current = true;
    try {
      const data = await ontologyApi.discover(projectId, selectedArtifactIds, true);
      setProgressPercent(0);
      setProgressStage('Starting');
      setRunId(data.run_id);
      setRun({ id: data.run_id, project_id: projectId, status: data.status, progress_percent: 0, run_logs: [] });
      setPolling(true);
      loadRunsHistory();
    } finally {
      discoverLock.current = false;
    }
  };

  const handleApprove = (elementType: string, elementIds: string[]) => {
    if (!versionId) return;
    ontologyApi.reviewApprove(versionId, elementType, elementIds).then(() => version && loadVersion(versionId));
  };

  const handleReject = (elementType: string, elementIds: string[]) => {
    if (!versionId) return;
    ontologyApi.reviewReject(versionId, elementType, elementIds).then(() => version && loadVersion(versionId));
  };

  const handleApproveVersionAndBuildGraph = async () => {
    if (!versionId) return;
    try {
      setPlatformLoading(true);
      setPlatformAction(null);
      const result = await platformApi.approveOntologyVersion(versionId, {
        approved_by: 'analyst',
        trigger_graph_build: true,
      });
      await loadVersion(versionId);
      const jobNote = result.graph_build_job_id ? ` Graph build job: ${result.graph_build_job_id}` : '';
      setPlatformAction(
        `Version approved.${jobNote}${result.fabric_id ? ` Linked fabric: ${result.fabric_id}` : ''}`,
      );
    } catch (err) {
      setPlatformAction(err instanceof Error ? err.message : 'Approve & build failed');
    } finally {
      setPlatformLoading(false);
    }
  };

  const handleDeleteProject = async () => {
    if (!projectId) return;
    if (!window.confirm('Delete this project? Its versions and runs will be removed.')) return;
    setDeletingProject(true);
    try {
      await ontologyApi.deleteProject(projectId);
      navigate('/ontology');
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to delete project');
    } finally {
      setDeletingProject(false);
    }
  };

  const buildContextualReply = (query: string): string => {
    const q = query.toLowerCase();
    if (!selectedElement) {
      return 'Select an entity, relationship, or attribute from the catalog to ask about it. I can then explain what it represents, its evidence, or how it fits in the ontology.';
    }
    if ('normalized_name' in selectedElement) {
      const entity = selectedElement as OntologyClass;
      const def = entity.definition?.trim();
      const evidence = entity.source_evidence?.slice(0, 1)?.[0]?.text_snippet?.trim();
      if (q.includes('represent') || q.includes('what is') || q.includes('mean') || q.includes('definition')) {
        if (def) return `${entity.normalized_name} represents: ${def}${evidence ? `\n\nEvidence from source: "${evidence.slice(0, 200)}${evidence.length > 200 ? '…' : ''}"` : ''}`;
        if (evidence) return `${entity.normalized_name} is an entity in this ontology. From the source: "${evidence.slice(0, 300)}${evidence.length > 300 ? '…' : ''}"`;
        return `${entity.normalized_name} is an entity (concept class) in this ontology. No definition or evidence snippet is stored yet. You can approve or edit it in Evidence & actions above.`;
      }
      if (def) return `${entity.normalized_name}: ${def}`;
      return `${entity.normalized_name} is an entity in this ontology. Confidence: ${Math.round((entity.confidence_score ?? 0) * 100)}%. Ask "What does this entity represent?" for a definition if available.`;
    }
    if ('relationship_name' in selectedElement) {
      const rel = selectedElement as OntologyRelationship;
      const src = version?.classes.find(c => c.id === rel.source_class_id)?.normalized_name ?? 'Source';
      const tgt = version?.classes.find(c => c.id === rel.target_class_id)?.normalized_name ?? 'Target';
      const evidence = (rel.evidence ?? [])?.slice(0, 1)?.[0]?.text_snippet?.trim();
      if (q.includes('represent') || q.includes('what is') || q.includes('mean') || q.includes('between')) {
        let ans = `This relationship links ${src} to ${tgt} as: "${rel.relationship_name}".`;
        if (rel.cardinality_if_detected) ans += ` Cardinality: ${rel.cardinality_if_detected}.`;
        if (evidence) ans += `\n\nEvidence: "${evidence.slice(0, 200)}${evidence.length > 200 ? '…' : ''}"`;
        return ans;
      }
      return `${src} —${rel.relationship_name}→ ${tgt}. Confidence: ${Math.round((rel.confidence_score ?? 0) * 100)}%.`;
    }
    if ('attribute_name' in selectedElement) {
      const attr = selectedElement as OntologyAttribute;
      const cls = version?.classes.find(c => c.id === attr.class_id)?.normalized_name ?? 'Entity';
      if (q.includes('represent') || q.includes('what is') || q.includes('mean')) {
        let ans = `"${attr.attribute_name}" is an attribute of ${cls}.`;
        if (attr.data_type_guess) ans += ` Data type: ${attr.data_type_guess}.`;
        if (attr.required_flag_guess) ans += ' It is marked as required.';
        return ans;
      }
      return `${attr.attribute_name} (${cls})${attr.data_type_guess ? ` · ${attr.data_type_guess}` : ''}. Confidence: ${Math.round((attr.confidence_score ?? 0) * 100)}%.`;
    }
    return 'I can explain the selected item—try "What does this entity represent?" or "What is this relationship?"';
  };

  const handleChatSend = () => {
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: q }]);
    setChatLoading(true);
    const history = chatMessages.map(m => ({ role: m.role, content: m.content }));
    let context: { selected_type: string; selected_name: string; selected_summary: string } | undefined;
    if (selectedElement) {
      if ('normalized_name' in selectedElement) {
        const e = selectedElement as OntologyClass;
        context = {
          selected_type: 'entity',
          selected_name: e.normalized_name,
          selected_summary: e.definition ? `Definition: ${e.definition}` : e.normalized_name,
        };
      } else if ('relationship_name' in selectedElement) {
        const r = selectedElement as OntologyRelationship;
        const src = version?.classes.find(c => c.id === r.source_class_id)?.normalized_name ?? r.source_class_id;
        const tgt = version?.classes.find(c => c.id === r.target_class_id)?.normalized_name ?? r.target_class_id;
        context = {
          selected_type: 'relationship',
          selected_name: r.relationship_name,
          selected_summary: `${src} — ${r.relationship_name} → ${tgt}`,
        };
      } else if ('attribute_name' in selectedElement) {
        const a = selectedElement as OntologyAttribute;
        const cls = version?.classes.find(c => c.id === a.class_id)?.normalized_name ?? a.class_id;
        context = {
          selected_type: 'attribute',
          selected_name: a.attribute_name,
          selected_summary: `${cls}.${a.attribute_name}${a.data_type_guess ? ` (${a.data_type_guess})` : ''}`,
        };
      }
    }
    ontologyApi
      .chat(versionId ?? null, q, context, history)
      .then(data => {
        setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      })
      .catch(() => {
        setChatMessages(prev => [...prev, { role: 'assistant', content: buildContextualReply(q) }]);
      })
      .finally(() => setChatLoading(false));
  };

  const downloadBlob = (content: string, filename: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleExportJson = () => {
    if (!versionId) return;
    ontologyApi.exportJson(versionId).then(res => {
      downloadBlob(
        JSON.stringify(res.data || res, null, 2),
        `ontology_${versionId}.json`,
        'application/json',
      );
    }).catch((err: unknown) => {
      setPlatformAction(err instanceof Error ? `JSON export failed: ${err.message}` : 'JSON export failed');
    });
  };

  const handleExportSemantic = async (format: 'rdf' | 'owl') => {
    if (!versionId) return;
    try {
      setPlatformLoading(true);
      const { text, filename, mime } = await ontologyApi.exportSemanticText(versionId, format);
      downloadBlob(text, filename, mime);
      setPlatformAction(`Downloaded ${format.toUpperCase()} export (${filename}).`);
    } catch (err: unknown) {
      setPlatformAction(
        err instanceof Error ? `${format.toUpperCase()} export failed: ${err.message}` : `${format.toUpperCase()} export failed`,
      );
    } finally {
      setPlatformLoading(false);
    }
  };

  const tabs: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'entities', label: 'Entities', icon: CubeIcon },
    { id: 'relationships', label: 'Relationships', icon: LinkIcon },
    { id: 'attributes', label: 'Attributes', icon: TagIcon },
    { id: 'rules', label: 'Rules', icon: DocumentMagnifyingGlassIcon },
    { id: 'canonical', label: 'Canonical model', icon: TableCellsIcon },
    { id: 'graph', label: 'Graph schema', icon: ShareIcon },
  ];
  const isFabricLinkedProject = React.useMemo(() => {
    const search = new URLSearchParams(location.search);
    if (search.get('source') === 'fabric') return true;
    return /created from knowledge fabric/i.test(projectDescription || '');
  }, [location.search, projectDescription]);
  const canRunFabricDiscovery = isFabricLinkedProject;
  const handleFabricDiscover = async () => {
    if (!projectId || !canRunFabricDiscovery) return;
    // Prefer the real fabric id (from project description / artifact metadata).
    // Do NOT use fabricLinkOrigins[0] — that is often "vector_documents", which
    // made schema discovery fail and silently fell through to document LLM
    // discovery (Record / Dataset / Medication).
    const fabricId = linkedFabricId;
    if (!fabricId) {
      setPlatformAction(
        'No linked fabric id found on this project. Re-create from the Knowledge Fabric, or run discovery from the fabric Knowledge Graph platform panel.',
      );
      return;
    }
    if (discoverLock.current || polling) return;
    discoverLock.current = true;
    try {
      setPlatformLoading(true);
      setPlatformAction(null);
      const { job_id } = await platformApi.discoverOntology(fabricId, true, projectId);
      setProgressPercent(0);
      setProgressStage('Starting');
      setTrackedJobId(job_id);
      setPolling(true);
      setPlatformAction('Schema discovery is running from the measured table profile.');
      loadRunsHistory();
    } catch (err: unknown) {
      setPlatformAction(
        err instanceof Error
          ? `Schema discovery failed: ${err.message}`
          : 'Schema discovery failed. Open the fabric Knowledge Graph → Enterprise platform → Run ontology discovery.',
      );
    } finally {
      discoverLock.current = false;
      setPlatformLoading(false);
    }
  };

  const graphNodeTypes = React.useMemo(
    () => (Array.isArray(graphData?.node_types) ? (graphData?.node_types as Record<string, unknown>[]) : []),
    [graphData]
  );
  const graphEdgeTypes = React.useMemo(
    () => (Array.isArray(graphData?.edge_types) ? (graphData?.edge_types as Record<string, unknown>[]) : []),
    [graphData]
  );
  const graphPathHints = React.useMemo(() => {
    const hints: Record<string, string> = {};
    const rawSchema = graphData?.graph_json_schema;
    if (!rawSchema) return hints;
    let schema: { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string }> } | null = null;
    if (typeof rawSchema === 'string') {
      try {
        schema = JSON.parse(rawSchema) as { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string }> };
      } catch {
        schema = null;
      }
    } else if (typeof rawSchema === 'object') {
      schema = rawSchema as { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string }> };
    }
    if (!schema?.nodes?.length || !schema.edges?.length) return hints;

    const incoming: Record<string, number> = {};
    const parents: Record<string, string[]> = {};
    schema.nodes.forEach((n) => {
      incoming[n.id] = 0;
      parents[n.id] = [];
    });
    schema.edges.forEach((e) => {
      incoming[e.to] = (incoming[e.to] ?? 0) + 1;
      if (!parents[e.to]) parents[e.to] = [];
      parents[e.to].push(e.from);
    });
    const roots = schema.nodes.filter((n) => (incoming[n.id] ?? 0) === 0).map((n) => n.id);
    const rootFallback = schema.nodes[0]?.id;

    const buildPath = (target: string): string => {
      const visited = new Set<string>();
      const queue: Array<{ node: string; path: string[] }> = (roots.length ? roots : [rootFallback]).filter(Boolean).map((r) => ({ node: r as string, path: [r as string] }));
      while (queue.length) {
        const current = queue.shift();
        if (!current) break;
        if (current.node === target) return current.path.join(' -> ');
        if (visited.has(current.node)) continue;
        visited.add(current.node);
        schema?.edges?.forEach((e) => {
          if (e.from === current.node && !visited.has(e.to)) {
            queue.push({ node: e.to, path: [...current.path, e.to] });
          }
        });
      }
      return target;
    };

    schema.nodes.forEach((n) => {
      hints[n.id] = buildPath(n.id);
      if (n.label) hints[n.label] = hints[n.id];
    });
    return hints;
  }, [graphData]);
  const graphSchemaCardNodes = React.useMemo(() => {
    const rawSchema = graphData?.graph_json_schema;
    let schema: { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string }> } | null = null;
    if (typeof rawSchema === 'string') {
      try {
        schema = JSON.parse(rawSchema) as { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string }> };
      } catch {
        schema = null;
      }
    } else if (rawSchema && typeof rawSchema === 'object') {
      schema = rawSchema as { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string }> };
    }

    if (schema?.nodes?.length) {
      return schema.nodes.map((n) => {
        const label = n.label ?? n.id;
        return {
          key: n.id,
          label,
          path: graphPathHints[n.id] ?? graphPathHints[label] ?? label,
          description: getGraphNodeDescription(label),
        };
      });
    }

    // Fallback to node_types when schema.nodes is not present.
    return graphNodeTypes.map((n, idx) => {
      const label = String(n.type ?? n.label ?? `node_${idx + 1}`);
      return {
        key: `${label}-${idx}`,
        label,
        path: graphPathHints[label] ?? label,
        description: getGraphNodeDescription(label),
      };
    });
  }, [graphData, graphNodeTypes, graphPathHints]);

  return (
    <div className="space-y-6 text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.bg-slate-50]:bg-white/[0.03] [&_.bg-teal-50]:bg-[rgba(94,200,242,0.08)] [&_.bg-cyan-50]:bg-[rgba(94,200,242,0.08)] [&_.bg-violet-50]:bg-[rgba(155,139,212,0.08)] [&_.bg-emerald-50]:bg-[rgba(62,207,155,0.08)] [&_.bg-teal-100]:bg-[rgba(94,200,242,0.16)] [&_.bg-cyan-100]:bg-[rgba(94,200,242,0.16)] [&_.bg-violet-100]:bg-[rgba(155,139,212,0.16)] [&_.bg-emerald-100]:bg-[rgba(62,207,155,0.16)] [&_.text-teal-800]:text-[#5ec8f2] [&_.text-teal-700]:text-[#5ec8f2] [&_.text-teal-600]:text-[#5ec8f2] [&_.text-teal-500]:text-[#5ec8f2] [&_.text-cyan-700]:text-[#5ec8f2] [&_.text-cyan-600]:text-[#5ec8f2] [&_.text-violet-700]:text-[#9b8bd4] [&_.text-violet-600]:text-[#9b8bd4] [&_.text-emerald-700]:text-[#3ecf9b] [&_.text-emerald-600]:text-[#3ecf9b] [&_.border-teal-200]:border-[rgba(94,200,242,0.25)] [&_.border-cyan-200]:border-[rgba(94,200,242,0.25)] [&_.border-violet-200]:border-[rgba(155,139,212,0.25)] [&_.border-emerald-200]:border-[rgba(62,207,155,0.25)] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.text-gray-300]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_.divide-gray-100]:divide-[rgba(148,163,184,0.09)] [&_.hover\:bg-gray-50:hover]:bg-white/[0.06] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_textarea]:bg-[#10141d]/70 [&_textarea]:text-[#e8edf4] [&_textarea]:border-[rgba(148,163,184,0.2)] [&_textarea]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => navigate('/ontology')}
          className="inline-flex items-center text-sm px-3 py-1.5 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#cbd5e1] hover:text-[#e8edf4] hover:bg-white/[0.06]"
        >
          <ArrowLeftIcon className="w-4 h-4 mr-1" />
          Back to Ontology
        </button>
        <h1 className="text-xl font-bold text-[#e8edf4] truncate flex-1">{projectName || 'Ontology Workspace'}</h1>
        {versionId && (
          <button
            type="button"
            onClick={handleApproveVersionAndBuildGraph}
            disabled={platformLoading}
            className="inline-flex items-center text-sm px-3 py-1.5 rounded-lg border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b] hover:bg-[rgba(62,207,155,0.22)] disabled:opacity-50"
            title="Approve entire version and enqueue canonical graph build"
          >
            <CheckIcon className="w-4 h-4 mr-1" />
            {platformLoading ? 'Approving…' : 'Approve & build graph'}
          </button>
        )}
        <button
          type="button"
          onClick={handleDeleteProject}
          disabled={deletingProject}
          className="inline-flex items-center text-sm px-3 py-1.5 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#8b9cb0] hover:text-[#f08984] hover:bg-white/[0.06] disabled:opacity-50"
          title="Delete project"
        >
          <TrashIcon className="w-5 h-5 mr-1" />
          Delete project
        </button>
      </div>

      {platformAction && (
        <div className="rounded-lg border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] px-4 py-2 text-sm text-[#cbd5e1]">
          {platformAction}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Source Artifacts panel - first column */}
        <div className="ontology-result or-shell p-4 border-[rgba(94,200,242,0.28)]">
          {isFabricLinkedProject ? (
            <>
              <h2 className="text-base font-semibold text-[#e8edf4] mb-1 flex items-center gap-2">
                <DocumentTextIcon className="w-5 h-5 text-[#5ec8f2]" />
                Fabric-linked source
              </h2>
              <p className="text-xs text-gray-500 mb-3">
                This ontology project was created from an existing Knowledge Fabric. For tabular Release 2.0 fabrics, discovery uses the measured table profile (not document co-occurrence).
              </p>
              <div className="py-4 px-3 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-600">
                <p className="font-medium text-gray-700">Using existing fabric context.</p>
                <p className="mt-1">
                  {linkedFabricId
                    ? `Linked fabric: ${linkedFabricId}`
                    : 'Fabric id missing from project metadata — recreate from the fabric.'}
                </p>
              </div>
              <button
                type="button"
                onClick={handleFabricDiscover}
                disabled={!canRunFabricDiscovery || polling || !linkedFabricId || platformLoading || runsHistory.some((r) => r.status === 'queued' || r.status === 'running')}
                className="mt-3 w-full inline-flex items-center justify-center px-3 py-2.5 rounded-xl bg-gradient-to-r from-[#5ec8f2] to-[#3ecf9b] text-[#061018] text-sm font-semibold hover:brightness-110 disabled:opacity-50 transition-all"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                {polling || platformLoading
                  ? progressPercent > 0
                    ? `Running… ${progressPercent}%${progressStage ? ` · ${progressStage}` : ''}`
                    : 'Starting…'
                  : 'Run schema discovery'}
              </button>
              {(polling || platformLoading) && (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#5ec8f2] to-[#3ecf9b] transition-[width] duration-500"
                    style={{ width: `${Math.max(progressPercent, 6)}%` }}
                  />
                </div>
              )}
              <p className="mt-2 text-xs text-gray-500">
                Expect entities like members / claims / plans with measured FK confidence — not Record / Dataset.
              </p>
              {fabricLinkOrigins.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {fabricLinkOrigins.map((origin) => (
                    <span
                      key={origin}
                      className="px-2 py-0.5 rounded-md text-[11px] border border-[rgba(148,163,184,0.24)] bg-white/[0.04] text-[#8b9cb0]"
                    >
                      source: {origin === 'processed_files' ? 'fabric files' : origin === 'vector_documents' ? 'fabric vector docs' : origin}
                    </span>
                  ))}
                </div>
              )}
              {run?.error_message && (
                <p className="mt-2 text-xs text-red-600">{run.error_message}</p>
              )}
            </>
          ) : (
            <>
              <h2 className="text-base font-semibold text-gray-900 mb-1 flex items-center gap-2">
                <DocumentTextIcon className="w-5 h-5 text-teal-500" />
                Source Artifacts
              </h2>
              <p className="text-xs text-gray-500 mb-3">Upload PDF, Word (DOCX), XML, or images (PNG, JPG, GIF, WEBP) here. Only files you upload in this panel are listed—no documents from Knowledge Fabric.</p>
              <label className="flex flex-col items-center justify-center w-full py-3 px-3 mb-3 rounded-lg border-2 border-dashed border-teal-300 bg-teal-50/50 cursor-pointer hover:bg-teal-50">
                <span className="text-sm font-medium text-teal-700">Upload PDF, DOCX, XML, or images</span>
                <input
                  type="file"
                  accept=".pdf,.docx,.xml,.png,.jpg,.jpeg,.gif,.webp"
                  multiple
                  onChange={handleUpload}
                  disabled={uploading}
                  className="hidden"
                />
                {uploading ? <span className="text-xs text-teal-600 mt-1">Uploading…</span> : <span className="text-xs text-gray-500 mt-1">Click or drop files</span>}
              </label>
              {uploadError && <p className="text-xs text-red-600 mb-2">{uploadError}</p>}
              {artifacts.length === 0 ? (
                <div className="py-4 px-3 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-600">
                  <p className="font-medium text-gray-700">No documents yet.</p>
                  <p className="mt-1">Upload PDF, Word (DOCX), XML, or image files (PNG, JPG, GIF, WEBP) using the button above.</p>
                </div>
              ) : (
              <ul className="space-y-1 max-h-48 overflow-y-auto">
                {artifacts.map(f => (
                  <li key={f.name}>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedArtifactIds.includes(f.name)}
                        onChange={() => setSelectedArtifactIds(prev => prev.includes(f.name) ? prev.filter(x => x !== f.name) : [...prev, f.name])}
                      />
                      <DocumentTextIcon className="w-4 h-4 text-gray-400" />
                      <span className="text-sm truncate">{f.name}</span>
                    </label>
                  </li>
                ))}
              </ul>
              )}
              <button
                type="button"
                onClick={handleDiscover}
                disabled={selectedArtifactIds.length === 0 || polling || runsHistory.some((r) => r.status === 'queued' || r.status === 'running')}
                className="mt-3 w-full inline-flex items-center justify-center px-3 py-2 rounded-lg bg-teal-600 text-white text-sm font-medium hover:bg-teal-700 disabled:opacity-50"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                {polling
                  ? progressPercent > 0
                    ? `Running… ${progressPercent}%${progressStage ? ` · ${progressStage}` : ''}`
                    : 'Starting…'
                  : 'Run discovery'}
              </button>
              {polling && (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#5ec8f2] to-[#3ecf9b] transition-[width] duration-500"
                    style={{ width: `${Math.max(progressPercent, 6)}%` }}
                  />
                </div>
              )}
              {artifacts.length > 0 && (
                <p className="mt-2 text-xs text-gray-500">{artifacts.length} file(s) available · {selectedArtifactIds.length} selected</p>
              )}
              {run?.error_message && (
                <p className="mt-2 text-xs text-red-600">{run.error_message}</p>
              )}
            </>
          )}
        </div>

        {/* Discovery history */}
        <div className="ontology-result or-shell p-4">
          <h2 className="text-sm font-semibold text-[#e8edf4] mb-1 flex items-center gap-2">
            <ClockIcon className="w-4 h-4 text-[#5ec8f2]" />
            Discovery history
          </h2>
          <p className="text-xs text-[#8b9cb0] mb-3">Past runs for this project. Open a completed run to enter the result studio.</p>
          <ul className="space-y-2 max-h-44 overflow-y-auto pr-1">
            {runsHistory.length === 0 ? (
              <li className="text-xs text-[#8b9cb0] rounded-xl border border-dashed border-[rgba(148,163,184,0.22)] px-3 py-4 text-center">
                No runs yet. Run discovery above.
              </li>
            ) : (
              runsHistory.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between gap-2 text-sm rounded-xl border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-3 py-2.5"
                >
                  <span className="truncate flex-1 min-w-0">
                    <span
                      className={`font-semibold ${
                        r.status === 'completed'
                          ? 'text-[#3ecf9b]'
                          : r.status === 'failed'
                            ? 'text-[#f08984]'
                            : 'text-[#5ec8f2]'
                      }`}
                    >
                      {r.status}
                    </span>
                    {r.completed_at && (
                      <span className="text-[#8b9cb0] ml-1.5 or-mono text-[11px]">
                        {(r.completed_at as string).slice(0, 19).replace('T', ' ')}
                      </span>
                    )}
                    {!r.completed_at && (r.status === 'queued' || r.status === 'running') && (
                      <span className="text-[#8b9cb0] ml-1.5 or-mono text-[11px]">
                        {clampPercent(r.progress_percent)}%
                        {r.current_stage ? ` · ${discoveryStageLabel(r.current_stage)}` : ''}
                      </span>
                    )}
                  </span>
                  {r.status === 'completed' && r.result_version_id && (
                    <button
                      type="button"
                      onClick={() => {
                        setVersionId(r.result_version_id!);
                        loadVersion(r.result_version_id!);
                      }}
                      className="or-view-cta shrink-0"
                    >
                      View result
                      <span aria-hidden>↗</span>
                    </button>
                  )}
                </li>
              ))
            )}
          </ul>
        </div>

        {/* Versions & Export */}
        <div className="ontology-result or-shell p-4">
          <h2 className="text-sm font-semibold text-[#e8edf4] mb-3">Versions & Export</h2>
          <select
            value={versionId || ''}
            onChange={e => { const v = e.target.value; setVersionId(v || null); if (v) loadVersion(v); }}
            className="block w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0a1018]/80 px-3 py-2 text-sm text-[#e8edf4]"
          >
            <option value="">Select version</option>
            {versions.map(v => (
              <option key={v.id} value={v.id}>{v.version_label} {v.is_draft ? '(draft)' : ''}</option>
            ))}
          </select>
          <div className="mt-3 flex flex-wrap gap-2">
            <a
              href={versionId ? ontologyApi.exportCsvUrl(versionId) : undefined}
              download
              className="inline-flex items-center px-3 py-1.5 rounded-xl border border-[rgba(94,200,242,0.28)] bg-[rgba(94,200,242,0.08)] text-sm text-[#bfeaff] hover:bg-[rgba(94,200,242,0.16)]"
            >
              CSV
            </a>
            <button
              type="button"
              onClick={handleExportJson}
              disabled={!versionId}
              className="inline-flex items-center px-3 py-1.5 rounded-xl border border-[rgba(62,207,155,0.28)] bg-[rgba(62,207,155,0.08)] text-sm text-[#7ee0b8] hover:bg-[rgba(62,207,155,0.16)] disabled:opacity-50"
            >
              <ArrowDownTrayIcon className="w-4 h-4 mr-1" />
              JSON
            </button>
            <button
              type="button"
              onClick={() => handleExportSemantic('rdf')}
              disabled={!versionId || platformLoading}
              className="inline-flex items-center px-3 py-1.5 rounded-xl border border-[rgba(94,200,242,0.32)] bg-[rgba(94,200,242,0.1)] text-sm text-[#bfeaff] hover:bg-[rgba(94,200,242,0.18)] disabled:opacity-50"
              title="Download RDF Schema as Turtle (.ttl)"
            >
              <ArrowDownTrayIcon className="w-4 h-4 mr-1" />
              RDF
            </button>
            <button
              type="button"
              onClick={() => handleExportSemantic('owl')}
              disabled={!versionId || platformLoading}
              className="inline-flex items-center px-3 py-1.5 rounded-xl border border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.12)] text-sm text-[#c4b8ef] hover:bg-[rgba(155,139,212,0.2)] disabled:opacity-50"
              title="Download OWL 2 ontology as Turtle (.owl.ttl)"
            >
              <ArrowDownTrayIcon className="w-4 h-4 mr-1" />
              OWL
            </button>
          </div>
          <p className="mt-2 text-[11px] text-[#8b9cb0]">
            RDF = RDFS Turtle · OWL = OWL 2 Turtle (classes, object/datatype properties)
          </p>
        </div>

        {/* Placeholder for third column */}
        <div />
      </div>

      {version && (
        <div className="ontology-result space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.2em] text-[#5ec8f2]/90">Result studio</p>
              <h2 className="text-xl font-semibold text-[#e8edf4] tracking-tight mt-0.5">
                Ontology surface
              </h2>
              <p className="text-xs text-[#8b9cb0] mt-1">
                Fluid review of entities, links, attributes, rules, and export models for this draft.
              </p>
            </div>
            <div className="or-tab-rail self-start sm:self-auto">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    setActiveTab(t.id);
                    setSelectedElement(null);
                  }}
                  className={`or-tab ${activeTab === t.id ? 'is-active' : ''}`}
                >
                  <t.icon className="w-3.5 h-3.5" />
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {(activeTab === 'canonical' || activeTab === 'graph') ? (
            <div className="space-y-6">
              {activeTab === 'canonical' && (
                <div className="or-shell overflow-hidden">
                  <ResultPanelHeader
                    icon={TableCellsIcon}
                    title="Canonical data model"
                    subtitle="Entity catalog, relationship matrix, attributes, and SQL-ready DDL"
                    countLabel={`${Array.isArray(canonicalData?.entity_catalog) ? (canonicalData?.entity_catalog as unknown[]).length : '—'} entities`}
                    tone="slate"
                  />
                  <div className="p-5 space-y-8">
                    {loadingCanonical && <p className="text-[#8b9cb0]">Loading canonical export…</p>}
                    {!loadingCanonical && canonicalData && (
                      <>
                        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          {[
                            { label: 'Entities', value: Array.isArray(canonicalData.entity_catalog) ? canonicalData.entity_catalog.length : 0, tone: 'text-[#5ec8f2]' },
                            { label: 'Relationships', value: Array.isArray(canonicalData.relationship_matrix) ? canonicalData.relationship_matrix.length : 0, tone: 'text-[#7ad4ff]' },
                            { label: 'Attributes', value: Array.isArray(canonicalData.attribute_catalog) ? canonicalData.attribute_catalog.length : 0, tone: 'text-[#c4b8ef]' },
                            { label: 'Suggested tables', value: Array.isArray(canonicalData.suggested_relational_tables) ? canonicalData.suggested_relational_tables.length : 0, tone: 'text-[#3ecf9b]' },
                          ].map((s) => (
                            <div key={s.label} className="or-stat">
                              <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">{s.label}</p>
                              <p className={`text-2xl font-semibold mt-1 ${s.tone}`}>{s.value}</p>
                            </div>
                          ))}
                        </section>
                        {Array.isArray(canonicalData.entity_catalog) && (canonicalData.entity_catalog as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3 flex items-center gap-2">
                              <CubeIcon className="w-4 h-4 text-[#5ec8f2]" />
                              Entity catalog
                            </h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                              {(canonicalData.entity_catalog as Record<string, unknown>[]).map((e: Record<string, unknown>, i: number) => (
                                <div key={i} className="or-card p-4" style={{ animationDelay: `${i * 40}ms` }}>
                                  <div className="font-medium text-[#e8edf4]">{String(e.name ?? e.normalized_name ?? '—')}</div>
                                  {e.definition ? <div className="text-xs text-[#8b9cb0] mt-1.5 line-clamp-2">{String(e.definition)}</div> : null}
                                </div>
                              ))}
                            </div>
                          </section>
                        )}
                        {Array.isArray(canonicalData.relationship_matrix) && (canonicalData.relationship_matrix as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3 flex items-center gap-2">
                              <LinkIcon className="w-4 h-4 text-[#5ec8f2]" />
                              Relationship matrix
                            </h3>
                            <div className="space-y-2">
                              {(canonicalData.relationship_matrix as Record<string, unknown>[]).map((r: Record<string, unknown>, i: number) => (
                                <div key={i} className="or-ribbon" style={{ animationDelay: `${i * 30}ms` }}>
                                  <span className="px-2.5 py-1 rounded-lg border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.1)] text-sm text-[#e8edf4]">
                                    {String(r.source ?? '—')}
                                  </span>
                                  <span className="or-mono text-[11px] text-[#5ec8f2]">{String(r.relationship ?? r.name ?? '—')}</span>
                                  <span className="text-[#8b9cb0]">→</span>
                                  <span className="px-2.5 py-1 rounded-lg border border-[rgba(62,207,155,0.3)] bg-[rgba(62,207,155,0.1)] text-sm text-[#d8f4e8]">
                                    {String(r.target ?? '—')}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </section>
                        )}
                        {Array.isArray(canonicalData.attribute_catalog) && (canonicalData.attribute_catalog as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3 flex items-center gap-2">
                              <TagIcon className="w-4 h-4 text-[#9b8bd4]" />
                              Attribute catalog
                            </h3>
                            <div className="rounded-2xl border border-[rgba(148,163,184,0.14)] overflow-hidden">
                              <table className="min-w-full text-sm">
                                <thead className="bg-white/[0.03]">
                                  <tr>
                                    <th className="px-4 py-2.5 text-left text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Entity</th>
                                    <th className="px-4 py-2.5 text-left text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Attribute</th>
                                    <th className="px-4 py-2.5 text-left text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Type</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-[rgba(148,163,184,0.08)]">
                                  {(canonicalData.attribute_catalog as Record<string, unknown>[]).map((a: Record<string, unknown>, i: number) => (
                                    <tr key={i} className="hover:bg-white/[0.03]">
                                      <td className="px-4 py-2.5 text-[#8b9cb0]">{String(a.entity ?? a.class ?? '—')}</td>
                                      <td className="px-4 py-2.5 font-medium text-[#e8edf4]">{String(a.name ?? a.attribute_name ?? '—')}</td>
                                      <td className="px-4 py-2.5 or-mono text-[11px] text-[#5ec8f2]">{String(a.data_type ?? a.type ?? '—')}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}
                        {canonicalData.suggested_sql_ddl && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3 flex items-center gap-2">
                              <TableCellsIcon className="w-4 h-4 text-[#3ecf9b]" />
                              Suggested SQL DDL
                            </h3>
                            <pre className="or-mono p-4 rounded-2xl border border-[rgba(62,207,155,0.22)] bg-[#070b12] text-[#b8f0d6] text-xs overflow-x-auto">
                              {String(canonicalData.suggested_sql_ddl)}
                            </pre>
                          </section>
                        )}
                        {(canonicalData.suggested_document_schema ?? canonicalData.document_schema) && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3">Document schema (JSON)</h3>
                            <pre className="or-mono p-4 rounded-2xl border border-[rgba(148,163,184,0.16)] bg-[#070b12] text-[#cbd5e1] text-xs overflow-x-auto max-h-64 overflow-y-auto">
                              {typeof (canonicalData.suggested_document_schema ?? canonicalData.document_schema) === 'string'
                                ? String(canonicalData.suggested_document_schema ?? canonicalData.document_schema)
                                : JSON.stringify(canonicalData.suggested_document_schema ?? canonicalData.document_schema, null, 2)}
                            </pre>
                          </section>
                        )}
                        {Array.isArray(canonicalData.suggested_relational_tables) && (canonicalData.suggested_relational_tables as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3">Suggested tables</h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                              {(canonicalData.suggested_relational_tables as Record<string, unknown>[]).map((t: Record<string, unknown>, i: number) => (
                                <div key={i} className="or-card px-3 py-3 text-sm">
                                  <p className="font-medium text-[#e8edf4]">{String(t.table_name ?? t.entity_id ?? '—')}</p>
                                  <p className="text-xs text-[#8b9cb0] mt-0.5">Relational table suggestion</p>
                                </div>
                              ))}
                            </div>
                          </section>
                        )}
                      </>
                    )}
                    {!loadingCanonical && !canonicalData && versionId && (
                      <p className="text-[#8b9cb0]">No canonical data. Run discovery and ensure a version is selected.</p>
                    )}
                  </div>
                </div>
              )}
              {activeTab === 'graph' && (
                <div className="or-shell overflow-hidden">
                  <ResultPanelHeader
                    icon={ShareIcon}
                    title="Graph-ready ontology"
                    subtitle="Node/edge blueprint with Cypher and JSON schema exports"
                    countLabel={`${graphNodeTypes.length} nodes`}
                    tone="cyan"
                  />
                  <div className="p-5 space-y-8">
                    {loadingGraph && <p className="text-[#8b9cb0]">Loading graph export…</p>}
                    {!loadingGraph && graphData && (
                      <>
                        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <div className="or-stat">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Node types</p>
                            <p className="text-2xl font-semibold text-[#5ec8f2] mt-1">{graphNodeTypes.length}</p>
                          </div>
                          <div className="or-stat">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Edge types</p>
                            <p className="text-2xl font-semibold text-[#c4b8ef] mt-1">{graphEdgeTypes.length}</p>
                          </div>
                          <div className="or-stat">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Graph schema</p>
                            <p className="text-sm font-semibold text-[#3ecf9b] mt-2">
                              {graphData.graph_json_schema ? 'Available' : 'Not available'}
                            </p>
                          </div>
                        </section>
                        {graphNodeTypes.length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3 flex items-center gap-2">
                              <CubeIcon className="w-4 h-4 text-[#5ec8f2]" />
                              Node types
                            </h3>
                            <div className="flex flex-wrap gap-2">
                              {graphNodeTypes.map((n: Record<string, unknown>, i: number) => {
                                const label = String(n.type ?? n.label ?? '—');
                                const isActive = activeGraphNode === label;
                                const description = getGraphNodeDescription(label);
                                const pathHint = graphPathHints[label] ?? label;
                                return (
                                  <button
                                    key={i}
                                    type="button"
                                    onClick={() => setActiveGraphNode(isActive ? null : label)}
                                    className={`group relative px-3 py-1.5 rounded-xl border text-sm font-medium transition-all ${
                                      isActive
                                        ? 'border-[rgba(62,207,155,0.55)] bg-[linear-gradient(120deg,rgba(62,207,155,0.24),rgba(94,200,242,0.16))] text-[#ecfff6]'
                                        : 'border-[rgba(94,200,242,0.28)] bg-white/[0.03] text-[#e8edf4] hover:border-[rgba(94,200,242,0.5)]'
                                    }`}
                                    title={description}
                                  >
                                    {label}
                                    <span className="pointer-events-none absolute z-20 left-1/2 -translate-x-1/2 top-full mt-2 w-72 rounded-xl border border-[rgba(148,163,184,0.28)] bg-[#070b12]/95 px-3 py-2 text-left opacity-0 group-hover:opacity-100 transition-opacity shadow-xl">
                                      <span className="block text-[11px] font-semibold text-[#bfeaff]">What it does</span>
                                      <span className="block text-[11px] text-[#cbd5e1] mt-1">{description}</span>
                                      <span className="block text-[11px] font-semibold text-[#7ad4c0] mt-2">Path preview</span>
                                      <span className="block text-[11px] text-[#9fb0c5] mt-1">{pathHint}</span>
                                    </span>
                                  </button>
                                );
                              })}
                            </div>
                            <p className="text-xs text-[#8b9cb0] mt-2">
                              Click a node to spotlight connected edges.
                              {activeGraphNode ? (
                                <span className="ml-1 text-[#3ecf9b] font-medium">Active: {activeGraphNode}</span>
                              ) : null}
                            </p>
                          </section>
                        )}
                        {graphEdgeTypes.length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3 flex items-center gap-2">
                              <LinkIcon className="w-4 h-4 text-[#5ec8f2]" />
                              Edge types
                            </h3>
                            <div className="space-y-2.5">
                              {graphEdgeTypes.map((e: Record<string, unknown>, i: number) => {
                                const source = String(e.source_type ?? e.from ?? '?');
                                const edgeLabel = String(e.edge_label ?? e.type ?? 'RELATES_TO');
                                const target = String(e.target_type ?? e.to ?? '?');
                                const connected = !activeGraphNode || activeGraphNode === source || activeGraphNode === target;
                                return (
                                  <div
                                    key={i}
                                    className={`or-ribbon transition-opacity ${connected ? 'opacity-100' : 'opacity-35'}`}
                                  >
                                    <span className="px-2.5 py-1 rounded-lg border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)] text-sm text-[#e8edf4]">
                                      {source}
                                    </span>
                                    <span className="or-mono text-[11px] text-[#c4b8ef]">{edgeLabel}</span>
                                    <span className="text-[#8b9cb0]">→</span>
                                    <span className="px-2.5 py-1 rounded-lg border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.12)] text-sm text-[#d8f4e8]">
                                      {target}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </section>
                        )}
                        {graphData.graph_cypher_snippet && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3">Cypher snippet</h3>
                            <pre className="or-mono p-4 rounded-2xl border border-[rgba(94,200,242,0.22)] bg-[#070b12] text-[#bfeaff] text-xs overflow-x-auto">
                              {String(graphData.graph_cypher_snippet)}
                            </pre>
                          </section>
                        )}
                        {graphData.graph_json_schema && (
                          <section>
                            <h3 className="text-sm font-semibold text-[#e8edf4] mb-3">Graph JSON schema cards</h3>
                            {graphSchemaCardNodes.length > 0 ? (
                              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                                {graphSchemaCardNodes.map((node) => (
                                  <button
                                    key={node.key}
                                    type="button"
                                    onClick={() => setActiveGraphNode(activeGraphNode === node.label ? null : node.label)}
                                    className={`or-card text-left p-3 ${activeGraphNode === node.label ? 'is-selected' : ''}`}
                                    title={node.description}
                                  >
                                    <p className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Schema node</p>
                                    <p className="text-base font-semibold text-[#e8edf4] mt-1">{node.label}</p>
                                    <p className="text-xs text-[#cbd5e1] mt-2">{node.description}</p>
                                    <p className="text-[11px] text-[#9fb0c5] mt-2 truncate" title={node.path}>
                                      Path: {node.path}
                                    </p>
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-[#8b9cb0]">Schema node cards are not available for this result.</p>
                            )}
                            <details className="mt-4 rounded-2xl border border-[rgba(148,163,184,0.16)] bg-[#0b0f16]">
                              <summary className="cursor-pointer px-4 py-2.5 text-xs font-medium text-[#8b9cb0]">
                                View raw Graph JSON schema
                              </summary>
                              <pre className="or-mono px-4 pb-4 text-xs overflow-x-auto max-h-72 overflow-y-auto text-[#cbd5e1]">
                                {typeof graphData.graph_json_schema === 'string'
                                  ? graphData.graph_json_schema
                                  : JSON.stringify(graphData.graph_json_schema, null, 2)}
                              </pre>
                            </details>
                          </section>
                        )}
                        {(Array.isArray(graphData.node_types) && (graphData.node_types as Record<string, unknown>[]).length > 0) ||
                        (Array.isArray(graphData.edge_types) && (graphData.edge_types as Record<string, unknown>[]).length > 0) ? (
                          <section>
                            <EntityConnectionsList
                              key={`connections-${versionId}`}
                              nodeTypes={(graphData.node_types as Record<string, unknown>[]) ?? []}
                              edgeTypes={(graphData.edge_types as Record<string, unknown>[]) ?? []}
                              graphJsonSchema={
                                graphData.graph_json_schema as
                                  | { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string; label?: string }> }
                                  | undefined
                              }
                            />
                          </section>
                        ) : null}
                      </>
                    )}
                    {!loadingGraph && !graphData && versionId && (
                      <p className="text-[#8b9cb0]">No graph data. Run discovery and ensure a version is selected.</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-2 or-shell overflow-hidden">
              {activeTab === 'entities' && (
                <div className="p-0">
                  <ResultPanelHeader
                    icon={CubeIcon}
                    title="Entity catalog"
                    subtitle="Concept classes extracted from measured schema / artifacts"
                    countLabel={`${version.classes.length} entities`}
                    tone="teal"
                  />
                  <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {version.classes.length === 0 && (
                      <div className="sm:col-span-2 rounded-2xl border border-dashed border-[rgba(148,163,184,0.22)] p-8 text-center text-sm text-[#8b9cb0]">
                        No entities available in this discovery result.
                      </div>
                    )}
                    {version.classes.map((c, idx) => (
                      <div
                        key={c.id}
                        onClick={() => setSelectedElement(c)}
                        className={`or-card cursor-pointer p-4 ${selectedElement?.id === c.id ? 'is-selected' : ''}`}
                        style={{ animationDelay: `${idx * 35}ms` }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)] text-[10px] font-bold text-[#bfeaff]">
                                {(c.normalized_name || '?').slice(0, 2).toUpperCase()}
                              </span>
                              <div className="font-semibold text-[#e8edf4] truncate">{c.normalized_name}</div>
                            </div>
                            {c.definition && <div className="text-xs text-[#8b9cb0] mt-2 line-clamp-2">{c.definition}</div>}
                          </div>
                          <StatusChip status={c.status} />
                        </div>
                        <div className="mt-3">
                          <ConfidenceMeter value={c.confidence_score} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {activeTab === 'relationships' && (
                <div className="p-0">
                  <ResultPanelHeader
                    icon={LinkIcon}
                    title="Relationship matrix"
                    subtitle="Semantic links between entity pairs"
                    countLabel={`${version.relationships.length} relations`}
                    tone="cyan"
                  />
                  <div className="p-4 space-y-2.5">
                    {version.relationships.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-[rgba(148,163,184,0.22)] p-8 text-center text-sm text-[#8b9cb0]">
                        No relationships available in this discovery result.
                      </div>
                    )}
                    {version.relationships.map((r, idx) => {
                      const src = version.classes.find((c) => c.id === r.source_class_id)?.normalized_name || r.source_class_id;
                      const tgt = version.classes.find((c) => c.id === r.target_class_id)?.normalized_name || r.target_class_id;
                      return (
                        <div
                          key={r.id}
                          onClick={() => setSelectedElement(r)}
                          className={`or-ribbon cursor-pointer ${selectedElement?.id === r.id ? 'ring-1 ring-[#5ec8f2]/60' : ''}`}
                          style={{ animationDelay: `${idx * 30}ms` }}
                        >
                          <span className="px-2.5 py-1 rounded-lg border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.1)] text-sm text-[#e8edf4]">
                            {src}
                          </span>
                          <span className="or-mono text-[11px] text-[#5ec8f2]">{r.relationship_name}</span>
                          <span className="text-[#8b9cb0]">→</span>
                          <span className="px-2.5 py-1 rounded-lg border border-[rgba(62,207,155,0.3)] bg-[rgba(62,207,155,0.1)] text-sm text-[#d8f4e8]">
                            {tgt}
                          </span>
                          <span className="ml-auto flex items-center gap-2">
                            <ConfidenceMeter value={r.confidence_score} />
                            <StatusChip status={r.status} />
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {activeTab === 'attributes' && (
                <div className="p-0">
                  <ResultPanelHeader
                    icon={TagIcon}
                    title="Attribute catalog"
                    subtitle="Properties and data types per entity"
                    countLabel={`${version.attributes.length} attributes`}
                    tone="violet"
                  />
                  <div className="p-4 space-y-2.5">
                    {version.attributes.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-[rgba(148,163,184,0.22)] p-8 text-center text-sm text-[#8b9cb0]">
                        No attributes available in this discovery result.
                      </div>
                    )}
                    {version.attributes.map((a, idx) => {
                      const cls = version.classes.find((c) => c.id === a.class_id)?.normalized_name || a.class_id;
                      const typeLabel = (a.data_type_guess || 'string').toLowerCase();
                      return (
                        <div
                          key={a.id}
                          onClick={() => setSelectedElement(a)}
                          className={`or-card cursor-pointer px-4 py-3 ${selectedElement?.id === a.id ? 'is-selected' : ''}`}
                          style={{ animationDelay: `${idx * 25}ms` }}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">{cls}</span>
                            <span className="text-[#3a4556]">/</span>
                            <span className="font-semibold text-[#e8edf4]">{a.attribute_name}</span>
                            {a.data_type_guess && (
                              <span className="or-mono px-2 py-0.5 rounded-md border border-[rgba(155,139,212,0.3)] bg-[rgba(155,139,212,0.1)] text-[#c4b8ef] text-[11px]">
                                {typeLabel}
                              </span>
                            )}
                            {a.required_flag_guess && (
                              <span className="px-2 py-0.5 rounded-md border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.12)] text-[#f08984] text-[10px] font-semibold uppercase tracking-wide">
                                required
                              </span>
                            )}
                            <span className="ml-auto flex items-center gap-2">
                              <ConfidenceMeter value={a.confidence_score} tone="lilac" />
                              <StatusChip status={a.status} />
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {activeTab === 'rules' && (
                <div className="p-0">
                  <ResultPanelHeader
                    icon={DocumentMagnifyingGlassIcon}
                    title="Business rules & constraints"
                    subtitle="Invariants and validation rules"
                    countLabel={`${version.constraints.length} rules`}
                    tone="emerald"
                  />
                  <div className="p-4 space-y-3">
                    {version.constraints.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-[rgba(148,163,184,0.22)] p-8 text-center text-sm text-[#8b9cb0]">
                        No business rules detected in this discovery result.
                      </div>
                    )}
                    {version.constraints.map((c) => (
                      <div key={c.id} className="or-card overflow-hidden">
                        <div className="px-4 py-2 border-b border-[rgba(62,207,155,0.2)] bg-[rgba(62,207,155,0.08)] flex items-center gap-2">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7ee0b8]">
                            {c.constraint_type}
                          </span>
                        </div>
                        <div className="or-mono px-4 py-3 text-sm text-[#d8f7eb] bg-[#070b12]/50 overflow-x-auto">
                          {c.expression}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Side panel */}
            <div className="flex flex-col gap-4 min-h-0 lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100vh-2rem)] lg:overflow-hidden lg:flex-1">
              <div className="or-shell overflow-hidden flex-shrink-0">
                <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.12)]">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Inspector</p>
                  <h3 className="text-sm font-semibold text-[#e8edf4] mt-0.5">Evidence & actions</h3>
                </div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  {selectedElement && (
                    <>
                      {'normalized_name' in selectedElement && (
                        <p className="text-sm font-semibold text-[#e8edf4]">{(selectedElement as OntologyClass).normalized_name}</p>
                      )}
                      {'relationship_name' in selectedElement && (
                        <p className="text-sm font-semibold text-[#e8edf4]">{(selectedElement as OntologyRelationship).relationship_name}</p>
                      )}
                      {'attribute_name' in selectedElement && (
                        <p className="text-sm font-semibold text-[#e8edf4]">{(selectedElement as OntologyAttribute).attribute_name}</p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <ConfidenceMeter value={selectedElement.confidence_score ?? 0} />
                        <StatusChip status={selectedElement.status} />
                        {(() => {
                          const src = (selectedElement as { extraction_source?: string }).extraction_source;
                          return src ? (
                            <span className="text-[10px] uppercase tracking-wide text-[#8b9cb0]">{src.replace('_', ' ')}</span>
                          ) : null;
                        })()}
                      </div>
                      {'normalized_name' in selectedElement && (selectedElement as OntologyClass).definition && (
                        <div className="mt-3">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">Definition</p>
                          <p className="text-xs text-[#cbd5e1] mt-1 line-clamp-3">{(selectedElement as OntologyClass).definition}</p>
                        </div>
                      )}
                      {'normalized_name' in selectedElement && (selectedElement as OntologyClass).aliases?.length ? (
                        <div className="mt-3">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">Aliases</p>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {((selectedElement as OntologyClass).aliases ?? []).map((a, i) => (
                              <span key={i} className="px-1.5 py-0.5 rounded-md border border-[rgba(148,163,184,0.2)] bg-white/[0.04] text-[#8b9cb0] text-[11px]">
                                {a}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {'relationship_name' in selectedElement && (
                        <>
                          {(selectedElement as OntologyRelationship).definition && (
                            <div className="mt-3">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">Definition</p>
                              <p className="text-xs text-[#cbd5e1] mt-1 line-clamp-2">
                                {(selectedElement as OntologyRelationship).definition}
                              </p>
                            </div>
                          )}
                          <div className="mt-3 or-ribbon text-xs">
                            <span className="text-[#e8edf4]">
                              {version?.classes.find((c) => c.id === (selectedElement as OntologyRelationship).source_class_id)?.normalized_name ??
                                (selectedElement as OntologyRelationship).source_class_id}
                            </span>
                            <span className="text-[#5ec8f2] or-mono">{(selectedElement as OntologyRelationship).relationship_name}</span>
                            <span className="text-[#d8f4e8]">
                              {version?.classes.find((c) => c.id === (selectedElement as OntologyRelationship).target_class_id)?.normalized_name ??
                                (selectedElement as OntologyRelationship).target_class_id}
                            </span>
                          </div>
                        </>
                      )}
                      {'attribute_name' in selectedElement && (
                        <div className="mt-3 space-y-1 text-xs text-[#8b9cb0]">
                          <p>
                            <span className="text-[#cbd5e1]">Entity:</span>{' '}
                            {version?.classes.find((c) => c.id === (selectedElement as OntologyAttribute).class_id)?.normalized_name ??
                              (selectedElement as OntologyAttribute).class_id}
                          </p>
                          {(selectedElement as OntologyAttribute).data_type_guess && (
                            <p>
                              <span className="text-[#cbd5e1]">Type:</span> {(selectedElement as OntologyAttribute).data_type_guess}
                            </p>
                          )}
                          {(selectedElement as OntologyAttribute).description && (
                            <p className="text-[#cbd5e1] mt-1 line-clamp-2">{(selectedElement as OntologyAttribute).description}</p>
                          )}
                        </div>
                      )}
                      {'source_evidence' in selectedElement && (selectedElement as OntologyClass).source_evidence?.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">Source evidence</p>
                          {(selectedElement as OntologyClass).source_evidence.slice(0, 3).map((ev, i) => (
                            <div key={i} className="p-2.5 rounded-xl border border-[rgba(148,163,184,0.14)] bg-white/[0.03] text-xs text-[#8b9cb0]">
                              {ev.text_snippet && <p className="line-clamp-3 text-[#cbd5e1]">{ev.text_snippet}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                      {'evidence' in selectedElement && ((selectedElement as OntologyRelationship).evidence?.length ?? 0) > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">Evidence</p>
                          {((selectedElement as OntologyRelationship).evidence ?? [])
                            .slice(0, 3)
                            .map((ev: { text_snippet?: string }, i: number) => (
                              <div key={i} className="p-2.5 rounded-xl border border-[rgba(148,163,184,0.14)] bg-white/[0.03] text-xs text-[#8b9cb0]">
                                {ev.text_snippet && <p className="line-clamp-3 text-[#cbd5e1]">{ev.text_snippet}</p>}
                              </div>
                            ))}
                        </div>
                      )}
                      {versionId && (
                        <div className="mt-4 pt-3 border-t border-[rgba(148,163,184,0.12)] flex gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              handleApprove(
                                activeTab === 'entities' ? 'class' : activeTab === 'relationships' ? 'relationship' : 'attribute',
                                [selectedElement.id],
                              )
                            }
                            className="inline-flex items-center px-3 py-2 rounded-xl border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b] text-sm font-medium hover:bg-[rgba(62,207,155,0.22)] transition-colors"
                          >
                            <CheckIcon className="w-4 h-4 mr-1.5" />
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              handleReject(
                                activeTab === 'entities' ? 'class' : activeTab === 'relationships' ? 'relationship' : 'attribute',
                                [selectedElement.id],
                              )
                            }
                            className="inline-flex items-center px-3 py-2 rounded-xl border border-[rgba(148,163,184,0.22)] bg-white/[0.03] text-[#8b9cb0] text-sm font-medium hover:text-[#f08984] transition-colors"
                          >
                            <XMarkIcon className="w-4 h-4 mr-1.5" />
                            Reject
                          </button>
                        </div>
                      )}
                    </>
                  )}
                  {!selectedElement && (
                    <p className="text-sm text-[#8b9cb0]">Select an entity, relationship, or attribute to inspect evidence.</p>
                  )}
                </div>
              </div>

              {version && (
                <div className="or-shell overflow-hidden flex-1 flex flex-col min-h-[280px]">
                  <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.12)] flex-shrink-0">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-xl border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.12)]">
                        <ChatBubbleLeftRightIcon className="w-4 h-4 text-[#5ec8f2]" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-[#e8edf4]">Real-time queries</h3>
                        <p className="text-xs text-[#8b9cb0] mt-0.5">Ask about this ontology</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex-1 flex flex-col min-h-0 p-3">
                    <div className="flex-1 overflow-y-auto space-y-3 mb-3 min-h-[120px]">
                      {chatMessages.length === 0 && (
                        <div className="text-center py-6 px-3">
                          <p className="text-sm text-[#8b9cb0]">
                            Ask anything about entities, relationships, attributes, or evidence.
                          </p>
                        </div>
                      )}
                      {chatMessages.map((msg, i) => (
                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                          <div
                            className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm ${
                              msg.role === 'user'
                                ? 'bg-gradient-to-br from-[#5ec8f2] to-[#3ecf9b] text-[#061018]'
                                : 'border border-[rgba(148,163,184,0.16)] bg-white/[0.04] text-[#cbd5e1]'
                            }`}
                          >
                            {msg.content}
                          </div>
                        </div>
                      ))}
                      {chatLoading && (
                        <div className="flex justify-start">
                          <div className="rounded-2xl px-3 py-2 text-sm border border-[rgba(148,163,184,0.16)] bg-white/[0.04] text-[#8b9cb0] animate-pulse">
                            Thinking…
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <input
                        type="text"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleChatSend();
                          }
                        }}
                        placeholder="Ask about this ontology…"
                        className="flex-1 rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0a1018]/80 px-3 py-2 text-sm text-[#e8edf4] placeholder:text-[#8b9cb0] focus:outline-none focus:ring-1 focus:ring-[#5ec8f2]/50"
                      />
                      <button
                        type="button"
                        onClick={handleChatSend}
                        disabled={!chatInput.trim() || chatLoading}
                        className="p-2 rounded-xl border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.16)] text-[#5ec8f2] hover:bg-[rgba(94,200,242,0.28)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        title="Send"
                      >
                        <PaperAirplaneIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          )}
        </div>
      )}

      {!version && versionId && <p className="text-gray-500">Loading version…</p>}
      {!version && !runId && versions.length === 0 && <p className="text-gray-500">Run discovery or select a version.</p>}
    </div>
  );
};

export default OntologyWorkspace;
