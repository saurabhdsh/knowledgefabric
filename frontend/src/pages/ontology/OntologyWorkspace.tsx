import React, { useCallback, useEffect, useState } from 'react';
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
  const toneClass =
    tone === 'cyan'
      ? 'bg-[rgba(94,200,242,0.16)] border-[rgba(94,200,242,0.32)] text-[#5ec8f2]'
      : tone === 'violet'
        ? 'bg-[rgba(155,139,212,0.16)] border-[rgba(155,139,212,0.32)] text-[#9b8bd4]'
        : tone === 'emerald'
          ? 'bg-[rgba(62,207,155,0.16)] border-[rgba(62,207,155,0.32)] text-[#3ecf9b]'
          : tone === 'slate'
            ? 'bg-white/[0.04] border-[rgba(148,163,184,0.24)] text-[#8b9cb0]'
            : 'bg-[rgba(94,200,242,0.16)] border-[rgba(94,200,242,0.32)] text-[#5ec8f2]';

  return (
    <div className="px-5 py-4 border-b border-[rgba(148,163,184,0.16)] bg-white/[0.04]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg border ${toneClass}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900">{title}</h3>
            <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
          </div>
        </div>
        <span className={`text-sm font-medium px-3 py-1 rounded-full border ${toneClass}`}>{countLabel}</span>
      </div>
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
              const meta = (a as unknown as { metadata?: { linked_from?: string } }).metadata;
              return meta?.linked_from;
            })
            .filter((v): v is string => Boolean(v))
        : [];
      setFabricLinkOrigins(Array.from(new Set(origins)));
    }).catch(() => {});
  }, [projectId]);

  const loadArtifacts = useCallback(() => {
    ontologyApi.getAvailableArtifacts().then(setArtifacts).catch(() => setArtifacts([]));
  }, []);

  const loadVersions = useCallback(() => {
    if (!projectId) return;
    ontologyApi.listVersions(projectId).then(setVersions).catch(() => setVersions([]));
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
    if (!runId || !projectId) return;
    const t = setInterval(() => {
      ontologyApi.getRun(projectId, runId).then(r => {
        setRun(r);
        if (r.status === 'completed' && r.result_version_id) {
          setPolling(false);
          setVersionId(r.result_version_id);
          loadVersions();
          loadVersion(r.result_version_id);
          loadRunsHistory();
        }
        if (r.status === 'failed') setPolling(false);
      }).catch(() => setPolling(false));
    }, 2000);
    return () => clearInterval(t);
  }, [runId, projectId, loadVersions, loadVersion, loadRunsHistory]);

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
    const data = await ontologyApi.discover(projectId, selectedArtifactIds, true);
    setRunId(data.run_id);
    setRun({ id: data.run_id, project_id: projectId, status: data.status, progress_percent: 0, run_logs: [] });
    setPolling(true);
    loadRunsHistory();
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

  const handleExportJson = () => {
    if (!versionId) return;
    ontologyApi.exportJson(versionId).then(res => {
      const blob = new Blob([JSON.stringify(res.data || res, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `ontology_${versionId}.json`;
      a.click();
    });
  };

  const tabs: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'entities', label: 'Entities', icon: CubeIcon },
    { id: 'relationships', label: 'Relationships', icon: LinkIcon },
    { id: 'attributes', label: 'Attributes', icon: TagIcon },
    { id: 'rules', label: 'Rules', icon: DocumentMagnifyingGlassIcon },
    { id: 'canonical', label: 'Canonical model', icon: TableCellsIcon },
    { id: 'graph', label: 'Graph schema', icon: ShareIcon },
  ];
  const tabActiveClass: Record<Tab, string> = {
    entities: 'border-[#5ec8f2] text-[#5ec8f2] bg-[rgba(94,200,242,0.08)]',
    relationships: 'border-[#67d7ff] text-[#67d7ff] bg-[rgba(103,215,255,0.1)]',
    attributes: 'border-[#b8a9ff] text-[#b8a9ff] bg-[rgba(184,169,255,0.1)]',
    rules: 'border-[#62e8b7] text-[#62e8b7] bg-[rgba(98,232,183,0.1)]',
    canonical: 'border-[#8b9cb0] text-[#cbd5e1] bg-white/[0.03]',
    graph: 'border-[#5ec8f2] text-[#5ec8f2] bg-[rgba(94,200,242,0.08)]',
  };
  const isFabricLinkedProject = React.useMemo(() => {
    const search = new URLSearchParams(location.search);
    if (search.get('source') === 'fabric') return true;
    return /created from knowledge fabric/i.test(projectDescription || '');
  }, [location.search, projectDescription]);
  const canRunFabricDiscovery = isFabricLinkedProject;
  const handleFabricDiscover = async () => {
    if (!projectId || !canRunFabricDiscovery) return;
    const fabricId = fabricLinkOrigins[0];
    if (fabricId) {
      try {
        setPlatformLoading(true);
        const { job_id } = await platformApi.discoverOntology(fabricId);
        setPlatformAction(`Schema discovery queued for fabric (${job_id})`);
        setPolling(true);
        loadRunsHistory();
        return;
      } catch {
        /* fall through to artifact discovery */
      } finally {
        setPlatformLoading(false);
      }
    }
    const data = await ontologyApi.discover(projectId, projectArtifactIds, true);
    setRunId(data.run_id);
    setRun({ id: data.run_id, project_id: projectId, status: data.status, progress_percent: 0, run_logs: [] });
    setPolling(true);
    loadRunsHistory();
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
        <div className="bg-white rounded-xl shadow-sm border-2 border-teal-200 p-4">
          {isFabricLinkedProject ? (
            <>
              <h2 className="text-base font-semibold text-gray-900 mb-1 flex items-center gap-2">
                <DocumentTextIcon className="w-5 h-5 text-teal-500" />
                Fabric-linked source
              </h2>
              <p className="text-xs text-gray-500 mb-3">
                This ontology project was created from an existing Knowledge Fabric. Source artifact upload is disabled for this project.
              </p>
              <div className="py-4 px-3 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-600">
                <p className="font-medium text-gray-700">Using existing fabric context.</p>
                <p className="mt-1">Select versions or discovery history on the right to review ontology outputs generated from the linked fabric.</p>
              </div>
              <button
                type="button"
                onClick={handleFabricDiscover}
                disabled={!canRunFabricDiscovery || polling}
                className="mt-3 w-full inline-flex items-center justify-center px-3 py-2 rounded-lg bg-teal-600 text-white text-sm font-medium hover:bg-teal-700 disabled:opacity-50"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                {polling ? `Running… ${run?.progress_percent ?? 0}%` : 'Run discovery'}
              </button>
              <p className="mt-2 text-xs text-gray-500">
                {canRunFabricDiscovery
                  ? (projectArtifactIds.length > 0
                      ? `${projectArtifactIds.length} linked artifact(s) available for discovery`
                      : 'No linked artifacts yet. Discovery will auto-resolve from linked fabric on run.')
                  : 'No linked source artifacts found for this fabric-linked project yet.'}
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
                disabled={selectedArtifactIds.length === 0 || polling}
                className="mt-3 w-full inline-flex items-center justify-center px-3 py-2 rounded-lg bg-teal-600 text-white text-sm font-medium hover:bg-teal-700 disabled:opacity-50"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                {polling ? `Running… ${run?.progress_percent ?? 0}%` : 'Run discovery'}
              </button>
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
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <ClockIcon className="w-4 h-4 text-teal-500" />
            Discovery history
          </h2>
          <p className="text-xs text-gray-500 mb-3">Past runs for this project. Completed runs can be opened to view the ontology version.</p>
          <ul className="space-y-2 max-h-40 overflow-y-auto">
            {runsHistory.length === 0 ? (
              <li className="text-xs text-gray-500">No runs yet. Run discovery above.</li>
            ) : (
              runsHistory.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2 text-sm border border-gray-100 rounded-lg px-2 py-1.5">
                  <span className="truncate flex-1">
                    <span className={`font-medium ${r.status === 'completed' ? 'text-green-600' : r.status === 'failed' ? 'text-red-600' : 'text-gray-700'}`}>
                      {r.status}
                    </span>
                    {r.completed_at && <span className="text-gray-500 ml-1">{(r.completed_at as string).slice(0, 19).replace('T', ' ')}</span>}
                    {r.started_at && !r.completed_at && <span className="text-gray-500 ml-1">Started {(r.started_at as string).slice(0, 19).replace('T', ' ')}</span>}
                  </span>
                  {r.status === 'completed' && r.result_version_id && (
                    <button
                      type="button"
                      onClick={() => { setVersionId(r.result_version_id!); loadVersion(r.result_version_id!); }}
                      className="text-xs text-[#5ec8f2] hover:underline shrink-0"
                    >
                      View result
                    </button>
                  )}
                </li>
              ))
            )}
          </ul>
        </div>

        {/* Versions & Export */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Versions & Export</h2>
          <select
            value={versionId || ''}
            onChange={e => { const v = e.target.value; setVersionId(v || null); if (v) loadVersion(v); }}
            className="block w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#10141d]/70 px-3 py-2 text-sm text-[#e8edf4]"
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
              className="inline-flex items-center px-3 py-1.5 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-sm text-[#cbd5e1] hover:bg-white/[0.06]"
            >
              CSV
            </a>
            <button
              type="button"
              onClick={handleExportJson}
              disabled={!versionId}
              className="inline-flex items-center px-3 py-1.5 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-sm text-[#cbd5e1] hover:bg-white/[0.06] disabled:opacity-50"
            >
              <ArrowDownTrayIcon className="w-4 h-4 mr-1" />
              JSON
            </button>
          </div>
        </div>

        {/* Placeholder for third column */}
        <div />
      </div>

      {version && (
        <>
          <div className="flex gap-2 border-b border-[rgba(148,163,184,0.11)]">
            {tabs.map(t => (
              <button
                key={t.id}
                type="button"
                onClick={() => { setActiveTab(t.id); setSelectedElement(null); }}
                className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px rounded-t-lg transition-colors ${activeTab === t.id ? tabActiveClass[t.id] : 'border-transparent text-[#8b9cb0] hover:text-[#cbd5e1]'}`}
              >
                <t.icon className="w-4 h-4 inline mr-1" />
                {t.label}
              </button>
            ))}
          </div>

          {(activeTab === 'canonical' || activeTab === 'graph') ? (
            <div className="space-y-6">
              {activeTab === 'canonical' && (
                <div className="bg-white rounded-xl shadow-sm border border-[rgba(148,163,184,0.18)] overflow-hidden">
                  <div className="px-5 py-4 border-b border-[rgba(148,163,184,0.16)] bg-white/[0.04]">
                    <h2 className="text-lg font-semibold text-gray-900">Canonical data model</h2>
                    <p className="text-sm text-gray-500 mt-0.5">Entity catalog, relationship matrix, attributes, and SQL-ready DDL</p>
                  </div>
                  <div className="p-5 space-y-8">
                    {loadingCanonical && <p className="text-gray-500">Loading canonical export…</p>}
                    {!loadingCanonical && canonicalData && (
                      <>
                        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <div className="rounded-xl border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Entities</p>
                            <p className="text-xl font-semibold text-[#e8edf4]">{Array.isArray(canonicalData.entity_catalog) ? canonicalData.entity_catalog.length : 0}</p>
                          </div>
                          <div className="rounded-xl border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Relationships</p>
                            <p className="text-xl font-semibold text-[#e8edf4]">{Array.isArray(canonicalData.relationship_matrix) ? canonicalData.relationship_matrix.length : 0}</p>
                          </div>
                          <div className="rounded-xl border border-[rgba(155,139,212,0.25)] bg-[rgba(155,139,212,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Attributes</p>
                            <p className="text-xl font-semibold text-[#e8edf4]">{Array.isArray(canonicalData.attribute_catalog) ? canonicalData.attribute_catalog.length : 0}</p>
                          </div>
                          <div className="rounded-xl border border-[rgba(62,207,155,0.25)] bg-[rgba(62,207,155,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Suggested tables</p>
                            <p className="text-xl font-semibold text-[#e8edf4]">{Array.isArray(canonicalData.suggested_relational_tables) ? canonicalData.suggested_relational_tables.length : 0}</p>
                          </div>
                        </section>
                        {Array.isArray(canonicalData.entity_catalog) && (canonicalData.entity_catalog as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                              <CubeIcon className="w-4 h-4 text-teal-500" />
                              Entity catalog
                            </h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                              {(canonicalData.entity_catalog as Record<string, unknown>[]).map((e: Record<string, unknown>, i: number) => (
                                <div key={i} className="p-4 rounded-xl border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow">
                                  <>
                                    <div className="font-medium text-gray-900">{String(e.name ?? e.normalized_name ?? '—')}</div>
                                    {e.definition ? <div className="text-xs text-gray-600 mt-1 line-clamp-2">{String(e.definition)}</div> : null}
                                  </>
                                </div>
                              ))}
                            </div>
                          </section>
                        )}
                        {Array.isArray(canonicalData.relationship_matrix) && (canonicalData.relationship_matrix as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                              <LinkIcon className="w-4 h-4 text-teal-500" />
                              Relationship matrix
                            </h3>
                            <div className="overflow-x-auto rounded-lg border border-gray-200">
                              <table className="min-w-full text-sm">
                                <thead className="bg-gray-50">
                                  <tr>
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Source</th>
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Relationship</th>
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Target</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                  {(canonicalData.relationship_matrix as Record<string, unknown>[]).map((r: Record<string, unknown>, i: number) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                      <td className="px-4 py-2 text-gray-900">{String(r.source ?? '—')}</td>
                                      <td className="px-4 py-2 text-teal-600 font-medium">{String(r.relationship ?? r.name ?? '—')}</td>
                                      <td className="px-4 py-2 text-gray-900">{String(r.target ?? '—')}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}
                        {Array.isArray(canonicalData.attribute_catalog) && (canonicalData.attribute_catalog as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                              <TagIcon className="w-4 h-4 text-teal-500" />
                              Attribute catalog
                            </h3>
                            <div className="rounded-lg border border-gray-200 overflow-hidden">
                              <table className="min-w-full text-sm">
                                <thead className="bg-gray-50">
                                  <tr>
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Entity</th>
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Attribute</th>
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Type</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                  {(canonicalData.attribute_catalog as Record<string, unknown>[]).map((a: Record<string, unknown>, i: number) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                      <td className="px-4 py-2 text-gray-600">{String(a.entity ?? a.class ?? '—')}</td>
                                      <td className="px-4 py-2 font-medium text-gray-900">{String(a.name ?? a.attribute_name ?? '—')}</td>
                                      <td className="px-4 py-2 text-gray-500">{String(a.data_type ?? a.type ?? '—')}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}
                        {canonicalData.suggested_sql_ddl && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                              <TableCellsIcon className="w-4 h-4 text-teal-500" />
                              Suggested SQL DDL
                            </h3>
                            <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-xs overflow-x-auto font-mono">{String(canonicalData.suggested_sql_ddl)}</pre>
                          </section>
                        )}
                        {(canonicalData.suggested_document_schema ?? canonicalData.document_schema) && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3">Document schema (JSON)</h3>
                            <pre className="p-4 rounded-xl bg-slate-800 text-slate-100 text-xs overflow-x-auto font-mono max-h-64 overflow-y-auto">{typeof (canonicalData.suggested_document_schema ?? canonicalData.document_schema) === 'string' ? String(canonicalData.suggested_document_schema ?? canonicalData.document_schema) : JSON.stringify(canonicalData.suggested_document_schema ?? canonicalData.document_schema, null, 2)}</pre>
                          </section>
                        )}
                        {Array.isArray(canonicalData.suggested_relational_tables) && (canonicalData.suggested_relational_tables as Record<string, unknown>[]).length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3">Suggested tables</h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                              {(canonicalData.suggested_relational_tables as Record<string, unknown>[]).map((t: Record<string, unknown>, i: number) => (
                                <div key={i} className="px-3 py-2 rounded-lg border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] text-sm">
                                  <p className="font-medium text-[#e8edf4]">{String(t.table_name ?? t.entity_id ?? '—')}</p>
                                  <p className="text-xs text-[#8b9cb0] mt-0.5">Relational table suggestion</p>
                                </div>
                              ))}
                            </div>
                          </section>
                        )}
                      </>
                    )}
                    {!loadingCanonical && !canonicalData && versionId && <p className="text-gray-500">No canonical data. Run discovery and ensure a version is selected.</p>}
                  </div>
                </div>
              )}
              {activeTab === 'graph' && (
                <div className="bg-white rounded-xl shadow-sm border border-[rgba(148,163,184,0.18)] overflow-hidden">
                  <div className="px-5 py-5 border-b border-[rgba(148,163,184,0.16)] bg-[radial-gradient(circle_at_top_right,rgba(94,200,242,0.22),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(155,139,212,0.18),transparent_38%)]">
                    <h2 className="text-lg font-semibold text-gray-900">Graph-ready ontology</h2>
                    <p className="text-sm text-gray-500 mt-0.5">Node/edge blueprint with Cypher and JSON schema exports</p>
                  </div>
                  <div className="p-5 space-y-8">
                    {loadingGraph && <p className="text-gray-500">Loading graph export…</p>}
                    {!loadingGraph && graphData && (
                      <>
                        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <div className="rounded-xl border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Node types</p>
                            <p className="text-2xl font-semibold text-[#e8edf4]">{graphNodeTypes.length}</p>
                          </div>
                          <div className="rounded-xl border border-[rgba(155,139,212,0.25)] bg-[rgba(155,139,212,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Edge types</p>
                            <p className="text-2xl font-semibold text-[#e8edf4]">{graphEdgeTypes.length}</p>
                          </div>
                          <div className="rounded-xl border border-[rgba(62,207,155,0.25)] bg-[rgba(62,207,155,0.08)] px-4 py-3">
                            <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Graph schema</p>
                            <p className="text-sm font-semibold text-[#e8edf4] mt-1">{graphData.graph_json_schema ? 'Available' : 'Not available'}</p>
                          </div>
                        </section>
                        {graphNodeTypes.length > 0 && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                              <CubeIcon className="w-4 h-4 text-indigo-500" />
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
                                    className={`group relative px-3 py-1.5 rounded-full border text-sm font-medium shadow-[0_0_0_1px_rgba(255,255,255,0.03)_inset] transition-all ${
                                      isActive
                                        ? 'border-[rgba(62,207,155,0.6)] bg-[linear-gradient(120deg,rgba(62,207,155,0.28),rgba(94,200,242,0.22))] text-[#ecfff6] shadow-[0_0_20px_rgba(62,207,155,0.25)]'
                                        : 'border-[rgba(94,200,242,0.35)] bg-[linear-gradient(120deg,rgba(94,200,242,0.2),rgba(155,139,212,0.18))] text-[#e8edf4] hover:scale-[1.02]'
                                    }`}
                                    title={description}
                                  >
                                    {label}
                                    <span className="pointer-events-none absolute z-20 left-1/2 -translate-x-1/2 top-full mt-2 w-72 rounded-xl border border-[rgba(148,163,184,0.28)] bg-[#070b12]/95 px-3 py-2 text-left opacity-0 group-hover:opacity-100 transition-opacity shadow-xl">
                                      <span className="block text-[11px] font-semibold text-[#bfeaff]">What it does</span>
                                      <span className="block text-[11px] text-[#cbd5e1] mt-1">{description}</span>
                                      <span className="block text-[11px] font-semibold text-[#d9d6f2] mt-2">Path preview</span>
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
                            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                              <LinkIcon className="w-4 h-4 text-indigo-500" />
                              Edge types
                            </h3>
                            <div className="space-y-3">
                              {graphEdgeTypes.map((e: Record<string, unknown>, i: number) => {
                                const source = String(e.source_type ?? e.from ?? '?');
                                const edgeLabel = String(e.edge_label ?? e.type ?? 'RELATES_TO');
                                const target = String(e.target_type ?? e.to ?? '?');
                                const connected = !activeGraphNode || activeGraphNode === source || activeGraphNode === target;
                                return (
                                  <div
                                    key={i}
                                    className={`rounded-xl border p-3 transition-all ${
                                      connected
                                        ? 'border-[rgba(94,200,242,0.28)] bg-[linear-gradient(135deg,rgba(16,20,29,0.94),rgba(20,27,39,0.85))] shadow-[0_0_22px_rgba(94,200,242,0.1)]'
                                        : 'border-[rgba(148,163,184,0.18)] bg-[rgba(16,20,29,0.45)] opacity-45'
                                    }`}
                                  >
                                    <div className="flex items-center gap-2 text-sm">
                                      <span className="inline-flex items-center px-2.5 py-1 rounded-md border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.15)] font-medium text-[#e8edf4]">
                                        {source}
                                      </span>
                                      <span className="text-[#8b9cb0]">→</span>
                                      <span className="inline-flex items-center px-2.5 py-1 rounded-md border border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.15)] text-[#d5cdf1] font-medium">
                                        {edgeLabel}
                                      </span>
                                      <span className="text-[#8b9cb0]">→</span>
                                      <span className="inline-flex items-center px-2.5 py-1 rounded-md border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.15)] font-medium text-[#d8f4e8]">
                                        {target}
                                      </span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </section>
                        )}
                        {graphData.graph_cypher_snippet && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3">Cypher snippet</h3>
                            <pre className="p-4 rounded-xl border border-[rgba(94,200,242,0.22)] bg-[#070b12] text-[#bfeaff] text-xs overflow-x-auto font-mono shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">{String(graphData.graph_cypher_snippet)}</pre>
                          </section>
                        )}
                        {graphData.graph_json_schema && (
                          <section>
                            <h3 className="text-sm font-semibold text-gray-700 mb-3">Graph JSON schema cards</h3>
                            {graphSchemaCardNodes.length > 0 ? (
                              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                                {graphSchemaCardNodes.map((node) => (
                                  <button
                                    key={node.key}
                                    type="button"
                                    onClick={() => setActiveGraphNode(activeGraphNode === node.label ? null : node.label)}
                                    className={`text-left rounded-xl border p-3 transition-all ${
                                      activeGraphNode === node.label
                                        ? 'border-[rgba(62,207,155,0.55)] bg-[linear-gradient(140deg,rgba(62,207,155,0.16),rgba(94,200,242,0.12))] shadow-[0_0_22px_rgba(62,207,155,0.2)]'
                                        : 'border-[rgba(155,139,212,0.24)] bg-[linear-gradient(140deg,rgba(12,16,24,0.88),rgba(18,23,33,0.75))] hover:border-[rgba(94,200,242,0.45)] hover:shadow-[0_0_20px_rgba(94,200,242,0.14)]'
                                    }`}
                                    title={node.description}
                                  >
                                    <p className="text-xs text-[#8b9cb0] uppercase tracking-wide">Schema node</p>
                                    <p className="text-base font-semibold text-[#e8edf4] mt-1">{node.label}</p>
                                    <p className="text-xs text-[#cbd5e1] mt-2">{node.description}</p>
                                    <p className="text-[11px] text-[#9fb0c5] mt-2 truncate" title={node.path}>
                                      Path: {node.path}
                                    </p>
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-500">Schema node cards are not available for this result.</p>
                            )}
                            <details className="mt-4 rounded-xl border border-[rgba(155,139,212,0.22)] bg-[#0b0f16]">
                              <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-[#d9d6f2]">
                                View raw Graph JSON schema
                              </summary>
                              <pre className="px-4 pb-4 text-xs overflow-x-auto font-mono max-h-72 overflow-y-auto text-[#d9d6f2]">
                                {typeof graphData.graph_json_schema === 'string' ? graphData.graph_json_schema : JSON.stringify(graphData.graph_json_schema, null, 2)}
                              </pre>
                            </details>
                          </section>
                        )}
                        {(Array.isArray(graphData.node_types) && (graphData.node_types as Record<string, unknown>[]).length > 0) || (Array.isArray(graphData.edge_types) && (graphData.edge_types as Record<string, unknown>[]).length > 0) ? (
                          <section>
                            <EntityConnectionsList
                              key={`connections-${versionId}`}
                              nodeTypes={(graphData.node_types as Record<string, unknown>[]) ?? []}
                              edgeTypes={(graphData.edge_types as Record<string, unknown>[]) ?? []}
                              graphJsonSchema={graphData.graph_json_schema as { nodes?: Array<{ id: string; label?: string }>; edges?: Array<{ from: string; to: string; label?: string }> } | undefined}
                            />
                          </section>
                        ) : null}
                      </>
                    )}
                    {!loadingGraph && !graphData && versionId && <p className="text-gray-500">No graph data. Run discovery and ensure a version is selected.</p>}
                  </div>
                </div>
              )}
            </div>
          ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-[rgba(148,163,184,0.18)] overflow-hidden">
              {activeTab === 'entities' && (
                <div className="p-0">
                  <ResultPanelHeader
                    icon={CubeIcon}
                    title="Entity catalog"
                    subtitle="Concept classes extracted from source artifacts"
                    countLabel={`${version.classes.length} entities`}
                    tone="teal"
                  />
                  <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {version.classes.length === 0 && (
                      <div className="sm:col-span-2 rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-6 text-center text-sm text-gray-500">
                        No entities available in this discovery result.
                      </div>
                    )}
                    {version.classes.map(c => {
                      const pct = Math.round(c.confidence_score * 100);
                      const confidenceColor = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-rose-400';
                      const statusColor = c.status === 'approved' ? 'bg-emerald-100 text-emerald-800' : c.status === 'rejected' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800';
                      return (
                        <div
                          key={c.id}
                          onClick={() => setSelectedElement(c)}
                          className={`relative overflow-hidden rounded-xl border cursor-pointer transition-all duration-200 ${selectedElement?.id === c.id ? 'ring-2 ring-[#5ec8f2] border-[rgba(94,200,242,0.55)] shadow-[0_0_24px_rgba(94,200,242,0.2)] bg-[linear-gradient(140deg,rgba(94,200,242,0.16),rgba(17,26,38,0.9))]' : 'border-gray-200 hover:border-teal-200 hover:shadow-sm bg-white'}`}
                        >
                          <div className={`absolute left-0 top-0 bottom-0 w-1 ${confidenceColor}`} />
                          <div className="pl-4 pr-4 py-4">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0 flex-1">
                                <div className="font-semibold text-gray-900 truncate">{c.normalized_name}</div>
                                {c.definition && <div className="text-xs text-gray-600 mt-1 line-clamp-2">{c.definition}</div>}
                              </div>
                              <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${statusColor}`}>{c.status}</span>
                            </div>
                            <div className="mt-3 flex items-center gap-2">
                              <div className="flex-1 h-1.5 rounded-full bg-gray-200 overflow-hidden">
                                <div className={`h-full rounded-full ${confidenceColor}`} style={{ width: `${pct}%` }} />
                              </div>
                              <span className="text-xs font-medium text-gray-500 tabular-nums">{pct}%</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
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
                  <div className="p-4 space-y-3">
                    {version.relationships.length === 0 && (
                      <div className="rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-6 text-center text-sm text-gray-500">
                        No relationships available in this discovery result.
                      </div>
                    )}
                    {version.relationships.map(r => {
                      const src = version.classes.find(c => c.id === r.source_class_id)?.normalized_name || r.source_class_id;
                      const tgt = version.classes.find(c => c.id === r.target_class_id)?.normalized_name || r.target_class_id;
                      const pct = Math.round(r.confidence_score * 100);
                      const statusColor = r.status === 'approved' ? 'bg-emerald-100 text-emerald-800' : r.status === 'rejected' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800';
                      return (
                        <div
                          key={r.id}
                          onClick={() => setSelectedElement(r)}
                          className={`rounded-xl border cursor-pointer transition-all duration-200 ${selectedElement?.id === r.id ? 'ring-2 ring-[#67d7ff] border-[rgba(103,215,255,0.55)] shadow-[0_0_24px_rgba(103,215,255,0.2)] bg-[linear-gradient(140deg,rgba(103,215,255,0.14),rgba(14,25,34,0.9))]' : 'border-gray-200 hover:border-cyan-200 hover:shadow-sm bg-white'}`}
                        >
                          <div className="px-4 py-3 flex flex-wrap items-center gap-2 sm:gap-3">
                            <span className="inline-flex items-center px-3 py-1 rounded-lg bg-slate-100 text-slate-800 text-sm font-medium">{src}</span>
                            <span className="flex items-center gap-1 text-cyan-600 font-semibold text-sm">
                              <span className="hidden sm:inline">—</span>
                              <span className="px-2 py-0.5 rounded bg-cyan-100">{r.relationship_name}</span>
                              <span className="text-gray-400">→</span>
                            </span>
                            <span className="inline-flex items-center px-3 py-1 rounded-lg bg-slate-100 text-slate-800 text-sm font-medium">{tgt}</span>
                            <span className="ml-auto flex items-center gap-2">
                              <span className="text-xs font-medium text-gray-500 tabular-nums">{pct}%</span>
                              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor}`}>{r.status}</span>
                            </span>
                          </div>
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
                  <div className="p-4 space-y-3">
                    {version.attributes.length === 0 && (
                      <div className="rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-6 text-center text-sm text-gray-500">
                        No attributes available in this discovery result.
                      </div>
                    )}
                    {version.attributes.map(a => {
                      const cls = version.classes.find(c => c.id === a.class_id)?.normalized_name || a.class_id;
                      const pct = Math.round(a.confidence_score * 100);
                      const statusColor = a.status === 'approved' ? 'bg-emerald-100 text-emerald-800' : a.status === 'rejected' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800';
                      const typeLabel = (a.data_type_guess || 'string').toLowerCase();
                      return (
                        <div
                          key={a.id}
                          onClick={() => setSelectedElement(a)}
                          className={`rounded-xl border cursor-pointer transition-all duration-200 ${selectedElement?.id === a.id ? 'ring-2 ring-[#b8a9ff] border-[rgba(184,169,255,0.55)] shadow-[0_0_24px_rgba(184,169,255,0.22)] bg-[linear-gradient(140deg,rgba(184,169,255,0.16),rgba(20,18,35,0.9))]' : 'border-gray-200 hover:border-violet-200 hover:shadow-sm bg-white'}`}
                        >
                          <div className="px-4 py-3 flex flex-wrap items-center gap-2">
                            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{cls}</span>
                            <span className="text-gray-300">/</span>
                            <span className="font-semibold text-gray-900">{a.attribute_name}</span>
                            {a.data_type_guess && (
                              <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-xs font-mono">{typeLabel}</span>
                            )}
                            {a.required_flag_guess && <span className="px-2 py-0.5 rounded-md bg-rose-100 text-rose-700 text-xs font-medium">required</span>}
                            <span className="ml-auto flex items-center gap-2">
                              <span className="text-xs font-medium text-gray-500 tabular-nums">{pct}%</span>
                              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor}`}>{a.status}</span>
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
                  <div className="p-4 space-y-4">
                    {version.constraints.length === 0 && (
                      <div className="rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-6 text-center text-sm text-gray-500">
                        No business rules detected in this discovery result.
                      </div>
                    )}
                    {version.constraints.map(c => (
                      <div
                        key={c.id}
                        className="rounded-xl border border-[rgba(98,232,183,0.28)] bg-[linear-gradient(140deg,rgba(98,232,183,0.08),rgba(16,22,24,0.88))] overflow-hidden hover:shadow-[0_0_20px_rgba(98,232,183,0.14)] transition-shadow"
                      >
                        <div className="px-4 py-2 bg-[rgba(98,232,183,0.12)] border-b border-[rgba(98,232,183,0.25)] flex items-center gap-2">
                          <span className="text-xs font-semibold uppercase tracking-wider text-[#62e8b7]">{c.constraint_type}</span>
                        </div>
                        <div className="px-4 py-3 font-mono text-sm text-[#d8f7eb] bg-[#0a1113]/65 overflow-x-auto">
                          {c.expression}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Side panel: sticky so query input stays in view without scrolling the page */}
            <div className="flex flex-col gap-4 min-h-0 lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100vh-2rem)] lg:overflow-hidden lg:flex-1">
              {/* Evidence & actions — compact, scrollable */}
              <div className="bg-white rounded-xl shadow-sm border border-[rgba(148,163,184,0.18)] overflow-hidden flex-shrink-0">
                <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.16)] bg-white/[0.04]">
                  <h3 className="text-sm font-semibold text-gray-900">Evidence & actions</h3>
                  <p className="text-xs text-gray-500 mt-0.5">Source references and approve</p>
                </div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  {selectedElement && (
                    <>
                      {/* Title */}
                      {'normalized_name' in selectedElement && (
                        <p className="text-sm font-semibold text-gray-900">{(selectedElement as OntologyClass).normalized_name}</p>
                      )}
                      {'relationship_name' in selectedElement && (
                        <p className="text-sm font-semibold text-gray-900">{(selectedElement as OntologyRelationship).relationship_name}</p>
                      )}
                      {'attribute_name' in selectedElement && (
                        <p className="text-sm font-semibold text-gray-900">{(selectedElement as OntologyAttribute).attribute_name}</p>
                      )}
                      {/* Metadata: confidence, status, extraction source */}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="text-xs text-gray-500 tabular-nums">
                          Confidence: {Math.round((selectedElement.confidence_score ?? 0) * 100)}%
                        </span>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${selectedElement.status === 'approved' ? 'bg-emerald-100 text-emerald-800' : selectedElement.status === 'rejected' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800'}`}>
                          {selectedElement.status}
                        </span>
                        {(() => {
                          const src = (selectedElement as { extraction_source?: string }).extraction_source;
                          return src ? <span className="text-xs text-gray-400 capitalize">{src.replace('_', ' ')}</span> : null;
                        })()}
                      </div>
                      {/* Entity: definition, aliases */}
                      {'normalized_name' in selectedElement && (selectedElement as OntologyClass).definition && (
                        <div className="mt-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Definition</p>
                          <p className="text-xs text-gray-700 mt-0.5 line-clamp-3">{(selectedElement as OntologyClass).definition}</p>
                        </div>
                      )}
                      {'normalized_name' in selectedElement && (selectedElement as OntologyClass).aliases?.length ? (
                        <div className="mt-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Aliases</p>
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {((selectedElement as OntologyClass).aliases ?? []).map((a, i) => (
                              <span key={i} className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 text-xs">{a}</span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {/* Relationship: definition, cardinality, source → target */}
                      {'relationship_name' in selectedElement && (
                        <>
                          {(selectedElement as OntologyRelationship).definition && (
                            <div className="mt-2">
                              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Definition</p>
                              <p className="text-xs text-gray-700 mt-0.5 line-clamp-2">{(selectedElement as OntologyRelationship).definition}</p>
                            </div>
                          )}
                          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
                            <span className="font-medium text-gray-700">{version?.classes.find(c => c.id === (selectedElement as OntologyRelationship).source_class_id)?.normalized_name ?? (selectedElement as OntologyRelationship).source_class_id}</span>
                            <span className="text-gray-400">→</span>
                            <span className="font-medium text-gray-700">{(selectedElement as OntologyRelationship).relationship_name}</span>
                            <span className="text-gray-400">→</span>
                            <span className="font-medium text-gray-700">{version?.classes.find(c => c.id === (selectedElement as OntologyRelationship).target_class_id)?.normalized_name ?? (selectedElement as OntologyRelationship).target_class_id}</span>
                            {(selectedElement as OntologyRelationship).cardinality_if_detected && (
                              <span className="ml-1 text-gray-500">({(selectedElement as OntologyRelationship).cardinality_if_detected})</span>
                            )}
                          </div>
                        </>
                      )}
                      {/* Attribute: description, type, required, owning entity */}
                      {'attribute_name' in selectedElement && (
                        <div className="mt-2 space-y-1 text-xs">
                          <p className="text-gray-500">
                            <span className="font-medium text-gray-600">Entity:</span> {version?.classes.find(c => c.id === (selectedElement as OntologyAttribute).class_id)?.normalized_name ?? (selectedElement as OntologyAttribute).class_id}
                          </p>
                          {(selectedElement as OntologyAttribute).data_type_guess && (
                            <p className="text-gray-500"><span className="font-medium text-gray-600">Type:</span> {(selectedElement as OntologyAttribute).data_type_guess}</p>
                          )}
                          {(selectedElement as OntologyAttribute).required_flag_guess && (
                            <span className="inline-block px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 text-xs">Required</span>
                          )}
                          {(selectedElement as OntologyAttribute).description && (
                            <p className="text-gray-700 mt-1 line-clamp-2">{(selectedElement as OntologyAttribute).description}</p>
                          )}
                        </div>
                      )}
                      {/* Source evidence (entities) */}
                      {'source_evidence' in selectedElement && (selectedElement as OntologyClass).source_evidence?.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Source evidence</p>
                          {(selectedElement as OntologyClass).source_evidence.slice(0, 3).map((ev, i) => (
                            <div key={i} className="p-2.5 rounded-lg border border-gray-100 bg-gray-50 text-xs text-gray-600">
                              <div className="flex flex-wrap gap-x-2 gap-y-0.5 mb-1">
                                {(ev as { artifact_type?: string }).artifact_type && <span className="font-medium text-gray-500 uppercase">{(ev as { artifact_type?: string }).artifact_type}</span>}
                                {(ev as { extraction_stage?: string }).extraction_stage && <span className="text-gray-400">{(ev as { extraction_stage?: string }).extraction_stage}</span>}
                                {ev.page_number != null && <span>Page {ev.page_number}</span>}
                                {ev.xml_path && <span className="text-gray-400 truncate">{ev.xml_path}</span>}
                              </div>
                              {ev.text_snippet && <p className="line-clamp-3">{ev.text_snippet}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Evidence (relationships & attributes) */}
                      {'evidence' in selectedElement && ((selectedElement as OntologyRelationship).evidence?.length ?? 0) > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Evidence</p>
                          {((selectedElement as OntologyRelationship).evidence ?? []).slice(0, 3).map((ev: { text_snippet?: string; xml_path?: string; artifact_type?: string; extraction_stage?: string }, i: number) => (
                            <div key={i} className="p-2.5 rounded-lg border border-gray-100 bg-gray-50 text-xs text-gray-600">
                              <div className="flex flex-wrap gap-x-2 gap-y-0.5 mb-1">
                                {ev.artifact_type && <span className="font-medium text-gray-500 uppercase">{ev.artifact_type}</span>}
                                {ev.extraction_stage && <span className="text-gray-400">{ev.extraction_stage}</span>}
                                {ev.xml_path && <span className="text-gray-400 truncate">{ev.xml_path}</span>}
                              </div>
                              {ev.text_snippet && <p className="line-clamp-3">{ev.text_snippet}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                      {versionId && (
                        <div className="mt-4 pt-3 border-t border-gray-100 flex gap-2">
                          <button
                            type="button"
                            onClick={() => handleApprove(activeTab === 'entities' ? 'class' : activeTab === 'relationships' ? 'relationship' : 'attribute', [selectedElement.id])}
                            className="inline-flex items-center px-3 py-2 rounded-lg bg-emerald-100 text-emerald-800 text-sm font-medium hover:bg-emerald-200 transition-colors"
                          >
                            <CheckIcon className="w-4 h-4 mr-1.5" />
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => handleReject(activeTab === 'entities' ? 'class' : activeTab === 'relationships' ? 'relationship' : 'attribute', [selectedElement.id])}
                            className="inline-flex items-center px-3 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200 transition-colors"
                          >
                            <XMarkIcon className="w-4 h-4 mr-1.5" />
                            Reject
                          </button>
                        </div>
                      )}
                    </>
                  )}
                  {!selectedElement && (
                    <p className="text-sm text-gray-500">Select an entity, relationship, or attribute to view evidence and approve.</p>
                  )}
                </div>
              </div>

              {/* Real-time conversation AI — visible when user has selected a result (version) */}
              {version && (
                <div className="bg-white rounded-xl shadow-sm border border-[rgba(148,163,184,0.18)] overflow-hidden flex-1 flex flex-col min-h-[280px]">
                  <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.16)] bg-white/[0.04] flex-shrink-0">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-[rgba(155,139,212,0.18)] border border-[rgba(155,139,212,0.3)]">
                        <ChatBubbleLeftRightIcon className="w-4 h-4 text-indigo-600" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-gray-900">Real-time queries</h3>
                        <p className="text-xs text-gray-500 mt-0.5">Ask about this ontology</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex-1 flex flex-col min-h-0 p-3">
                    <div className="flex-1 overflow-y-auto space-y-3 mb-3 min-h-[120px]">
                      {chatMessages.length === 0 && (
                        <div className="text-center py-6 px-3">
                          <p className="text-sm text-gray-500">Ask anything about the discovery result: entities, relationships, attributes, or evidence.</p>
                          <p className="text-xs text-gray-400 mt-2">e.g. &quot;What does this entity represent?&quot;</p>
                        </div>
                      )}
                      {chatMessages.map((msg, i) => (
                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[90%] rounded-xl px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-800 border border-gray-200'}`}>
                            {msg.content}
                          </div>
                        </div>
                      ))}
                      {chatLoading && (
                        <div className="flex justify-start">
                          <div className="rounded-xl px-3 py-2 text-sm bg-gray-100 text-gray-500 border border-gray-200 animate-pulse">
                            Thinking…
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <input
                        type="text"
                        value={chatInput}
                        onChange={e => setChatInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend(); } }}
                        placeholder="Ask about this ontology…"
                        className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      />
                      <button
                        type="button"
                        onClick={handleChatSend}
                        disabled={!chatInput.trim() || chatLoading}
                        className="p-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
        </>
      )}

      {!version && versionId && <p className="text-gray-500">Loading version…</p>}
      {!version && !runId && versions.length === 0 && <p className="text-gray-500">Run discovery or select a version.</p>}
    </div>
  );
};

export default OntologyWorkspace;
