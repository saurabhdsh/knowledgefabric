import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import * as d3 from 'd3';
import { apiRequest, authenticatedFetch, getApiUrl } from '../utils/api';
import { renderLlmGraphInsight } from '../utils/renderLlmGraphInsight';
import FabricPlatformPanel from '../components/FabricPlatformPanel';
import { getWeaveDomain } from '../utils/weaveDomain';
import {
  PHARMA_GRAPH_VIEWS,
  labelMatchesPharmaLens,
  shouldShowPharmaGraphUi,
  type PharmaGraphLens,
} from '../utils/pharmaGraphLens';

type GraphNodeType = 'fabric' | 'collection' | 'entity' | 'class' | 'code' | 'workspace';

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: GraphNodeType;
  weight: number;
  group?: string;
  properties?: Record<string, unknown>;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  relation: string;
  weight: number;
  properties?: Record<string, unknown>;
}

interface GraphViewOption {
  id: string;
  label: string;
  graph_type?: string;
  node_count?: number;
  edge_count?: number;
}

interface GraphAnalytics {
  top_entities: Array<{ label: string; weight: number }>;
  top_relationships: Array<{ source: string; target: string; weight: number }>;
  relationship_breakdown: Record<string, number>;
  entity_count: number;
  graph_density: number;
}

interface FabricDetails {
  id: string;
  name: string;
  source_type: string;
  status: string;
  model_status?: string;
  document_count: number;
  total_chunks: number;
  description?: string;
  tags?: string[];
  updated_at?: string;
  weave_domain?: string;
  connector_profile?: string | null;
  ontology_project_id?: string | null;
  approved_ontology_version_id?: string | null;
  discovery_summary?: string;
  migration_blueprint?: {
    narrative?: string;
    waves?: Array<{ name?: string; modules?: string[]; intent?: string }>;
    risks?: Array<{ severity?: string; message?: string; type?: string }>;
    bounded_contexts?: Array<{ name?: string; description?: string }>;
  };
  codebase?: Record<string, unknown>;
  guardrails?: {
    data_classification?: string;
    compliance_tags?: string[];
    pii_fields?: string[];
    enforce_masking?: boolean;
    encryption_at_rest?: boolean;
    encryption_in_transit?: boolean;
    row_level_security?: boolean;
    approved_roles?: string[];
  };
}

interface FabricGuardrails {
  data_classification: 'public' | 'internal' | 'confidential' | 'restricted';
  compliance_tags: string[];
  pii_fields: string[];
  enforce_masking: boolean;
  encryption_at_rest: boolean;
  encryption_in_transit: boolean;
  row_level_security: boolean;
  approved_roles: string[];
}

interface LLMInsight {
  generated: boolean;
  summary: string;
}

type GraphViewType =
  | 'canonical'
  | 'profiled_schema'
  | 'database_schema'
  | 'stale_schema'
  | 'exploratory'
  | 'codebase';

const GRAPH_TYPE_LABELS: Record<string, string> = {
  canonical: 'Ontology (approved classes)',
  profiled_schema: 'Data profile (measured FKs + samples)',
  database_schema: 'Database schema (legacy)',
  stale_schema: 'Schema stub — rebuild fabric for measured FKs',
  exploratory: 'Exploratory (co-occurrence)',
  codebase: 'Code structure',
};

function coerceNodeType(raw: unknown): GraphNodeType {
  const t = String(raw || '').toLowerCase();
  if (t === 'fabric' || t === 'workspace') return 'fabric';
  if (t === 'collection' || t === 'table') return 'collection';
  if (t === 'class' || t === 'ontology_class') return 'class';
  if (t === 'entity' || t === 'instance') return 'entity';
  if (t === 'code' || t === 'module' || t === 'file' || t === 'symbol' || t === 'node') return 'code';
  // Heuristic from id prefixes used by the backend builders.
  return 'entity';
}

function normalizeGraphPayload(data: Record<string, unknown>): {
  nodes: GraphNode[];
  edges: GraphEdge[];
  graphType: GraphViewType;
  ontologyVersionId?: string;
  graphNote?: string;
  availableViews: GraphViewOption[];
  activeView: string;
  rebuildRequired: boolean;
  sampleSize?: number;
  sampleTotal?: number;
  sampleCapped?: boolean;
} {
  const graphType = (data.graph_type as GraphViewType) || 'exploratory';
  const rawNodes = (data.nodes as Array<Record<string, unknown>>) || [];
  const rawEdges = (data.edges as Array<Record<string, unknown>>) || [];

  const nodes: GraphNode[] = rawNodes.map((n) => {
    const id = String(n.id);
    let type = coerceNodeType(n.type);
    if (id.startsWith('collection:')) type = 'collection';
    else if (id.startsWith('instance:')) type = 'entity';
    else if (id.startsWith('fabric:')) type = 'fabric';
    return {
      id,
      label: String(n.label || n.normalized_name || n.id),
      type,
      weight: Number(n.weight ?? 1),
      group: n.group != null ? String(n.group) : undefined,
      properties: (n.properties as Record<string, unknown>) || {},
    };
  });

  const edges: GraphEdge[] = rawEdges.map((e) => ({
    source: String(e.source),
    target: String(e.target),
    relation: String(e.relation || e.label || e.type || e.relationship_type || 'relates_to'),
    weight: Number(e.weight ?? 1),
    properties: (e.properties as Record<string, unknown>) || {
      confidence: e.confidence,
      evidence_refs: e.evidence_refs,
    },
  }));

  return {
    nodes,
    edges,
    graphType,
    ontologyVersionId: data.ontology_version_id as string | undefined,
    graphNote: data.graph_note as string | undefined,
    availableViews: (data.available_views as GraphViewOption[]) || [],
    activeView: String(data.active_view || 'data'),
    rebuildRequired: Boolean(data.rebuild_required),
    sampleSize: data.document_sample_size as number | undefined,
    sampleTotal: data.document_total as number | undefined,
    sampleCapped: data.document_sample_capped as boolean | undefined,
  };
}

const FabricKnowledgeGraph: React.FC = () => {
  const { fabricId } = useParams();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const rootGroupRef = useRef<d3.Selection<SVGGElement, unknown, null, undefined> | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [fabricName, setFabricName] = useState<string>('Knowledge Fabric');
  const [fabricDetails, setFabricDetails] = useState<FabricDetails | null>(null);
  const [analytics, setAnalytics] = useState<GraphAnalytics | null>(null);
  const [llmInsight, setLlmInsight] = useState<LLMInsight | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showMentions, setShowMentions] = useState(true);
  const [showRelated, setShowRelated] = useState(true);
  const [showOtherRelations, setShowOtherRelations] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [focusHops, setFocusHops] = useState<0 | 1 | 2>(0);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [renameSaving, setRenameSaving] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [isEditingGuardrails, setIsEditingGuardrails] = useState(false);
  const [guardrailsSaving, setGuardrailsSaving] = useState(false);
  const [guardrailsError, setGuardrailsError] = useState<string | null>(null);
  const [guardrailsForm, setGuardrailsForm] = useState<FabricGuardrails>({
    data_classification: 'internal',
    compliance_tags: [],
    pii_fields: [],
    enforce_masking: true,
    encryption_at_rest: true,
    encryption_in_transit: true,
    row_level_security: false,
    approved_roles: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pharmaLens, setPharmaLens] = useState<PharmaGraphLens>('full');
  const [graphType, setGraphType] = useState<GraphViewType>('exploratory');
  const [ontologyVersionId, setOntologyVersionId] = useState<string | undefined>();
  const [graphReloadKey, setGraphReloadKey] = useState(0);
  const [graphNote, setGraphNote] = useState<string | null>(null);
  const [availableViews, setAvailableViews] = useState<GraphViewOption[]>([]);
  const [activeView, setActiveView] = useState<string>('auto');
  const [rebuildRequired, setRebuildRequired] = useState(false);
  const [sampleMeta, setSampleMeta] = useState<{ size?: number; total?: number; capped?: boolean }>({});
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  /** Server-side focus neighborhood for canonical ontology graphs (null = use client BFS). */
  const [serverFocusIds, setServerFocusIds] = useState<Set<string> | null>(null);

  const showPharmaGraphUi = shouldShowPharmaGraphUi(getWeaveDomain(), fabricDetails);

  const loadGraph = useCallback(async () => {
    if (!fabricId) return;
    try {
      setLoading(true);
      setError(null);
      setSelectedNode(null);
      setSelectedEdge(null);
      const viewParam = activeView && activeView !== 'auto' ? `&view=${encodeURIComponent(activeView)}` : '';
      const response = await apiRequest(
        `api/v1/knowledge/${fabricId}/knowledge-graph?include_llm=true${viewParam}`
      );
      if (response.status === 401) {
        throw new Error('Session expired after a long fabric create. Sign in again, then reopen this fabric from Available Fabrics.');
      }
      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.detail || payload?.message || payload?.error || `Request failed: ${response.status}`);
      }
      const data = payload.data || {};
      const normalized = normalizeGraphPayload(data);
      setFabricName(String(data.fabric_name || 'Knowledge Fabric'));
      setNodes(normalized.nodes);
      setEdges(normalized.edges);
      setGraphType(normalized.graphType);
      setOntologyVersionId(normalized.ontologyVersionId);
      setGraphNote(normalized.graphNote || null);
      setAvailableViews(normalized.availableViews);
      setRebuildRequired(normalized.rebuildRequired);
      setSampleMeta({
        size: normalized.sampleSize,
        total: normalized.sampleTotal,
        capped: normalized.sampleCapped,
      });
      // Reflect the server-chosen view on first load without re-fetching.
      setActiveView((prev) => (prev === 'auto' ? normalized.activeView || 'data' : prev));
      setAnalytics((data.analytics as GraphAnalytics) || null);
      setLlmInsight((data.llm_insight as LLMInsight) || null);
      setFabricDetails((data.fabric_details as FabricDetails) || null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [fabricId, activeView]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph, graphReloadKey]);

  // Canonical focus: use persisted Postgres neighbors (bidirectional) so hops
  // match the stored ontology graph, not only the client adjacency copy.
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (
        graphType !== 'canonical' ||
        focusHops <= 0 ||
        !selectedNode ||
        !fabricId
      ) {
        setServerFocusIds(null);
        return;
      }
      try {
        const versionQs = ontologyVersionId
          ? `&ontology_version_id=${encodeURIComponent(ontologyVersionId)}`
          : '';
        const response = await apiRequest(
          `api/v1/graph/fabrics/${fabricId}/graph/neighbors/${encodeURIComponent(selectedNode.id)}?hops=${focusHops}${versionQs}`
        );
        const payload = await response.json();
        if (!response.ok || !payload?.success) {
          setServerFocusIds(null);
          return;
        }
        const ids = new Set<string>(
          ((payload.data?.nodes as Array<{ id?: string }>) || [])
            .map((n) => String(n.id || ''))
            .filter(Boolean)
        );
        ids.add(selectedNode.id);
        if (!cancelled) setServerFocusIds(ids);
      } catch {
        if (!cancelled) setServerFocusIds(null);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [graphType, focusHops, selectedNode, fabricId, ontologyVersionId]);

  const graphStats = useMemo(
    () => ({
      nodes: nodes.length,
      edges: edges.length,
      entities: nodes.filter((n) => n.type === 'entity').length,
      collections: nodes.filter((n) => n.type === 'collection').length,
      classes: nodes.filter((n) => n.type === 'class').length,
    }),
    [nodes, edges]
  );

  const relationFilteredGraph = useMemo(() => {
    const knownIds = new Set(nodes.map((n) => n.id));
    let relationFiltered = edges.filter((e) => {
      const src = typeof e.source === 'string' ? e.source : e.source?.id;
      const dst = typeof e.target === 'string' ? e.target : e.target?.id;
      if (!src || !dst || !knownIds.has(src) || !knownIds.has(dst)) return false;
      if (e.relation === 'mentions') return showMentions;
      if (e.relation === 'related_to') return showRelated;
      return showOtherRelations;
    });

    let nodesAllowed = new Set(nodes.map((n) => n.id));

    if (focusHops > 0 && selectedNode) {
      if (serverFocusIds && serverFocusIds.size > 0) {
        nodesAllowed = new Set(serverFocusIds);
      } else {
        const adjacency = new Map<string, Set<string>>();
        for (const edge of relationFiltered) {
          const src = typeof edge.source === 'string' ? edge.source : edge.source.id;
          const dst = typeof edge.target === 'string' ? edge.target : edge.target.id;
          if (!adjacency.has(src)) adjacency.set(src, new Set());
          if (!adjacency.has(dst)) adjacency.set(dst, new Set());
          adjacency.get(src)!.add(dst);
          adjacency.get(dst)!.add(src);
        }
        const visited = new Set<string>([selectedNode.id]);
        let frontier = new Set<string>([selectedNode.id]);
        for (let hop = 0; hop < focusHops; hop += 1) {
          const next = new Set<string>();
          frontier.forEach((id) => {
            (adjacency.get(id) || new Set()).forEach((nbr) => {
              if (!visited.has(nbr)) {
                visited.add(nbr);
                next.add(nbr);
              }
            });
          });
          frontier = next;
        }
        nodesAllowed = visited;
      }
      relationFiltered = relationFiltered.filter((e) => {
        const src = typeof e.source === 'string' ? e.source : e.source.id;
        const dst = typeof e.target === 'string' ? e.target : e.target.id;
        return nodesAllowed.has(src) && nodesAllowed.has(dst);
      });
    }

    const nodeFiltered = nodes.filter((n) => nodesAllowed.has(n.id));
    return { nodes: nodeFiltered, edges: relationFiltered };
  }, [nodes, edges, showMentions, showRelated, showOtherRelations, focusHops, selectedNode, serverFocusIds]);

  const visibleGraph = useMemo(() => {
    if (!showPharmaGraphUi || pharmaLens === 'full') return relationFilteredGraph;
    const allowedIds = new Set<string>();
    relationFilteredGraph.nodes.forEach((n) => {
      if (n.type === 'fabric' || labelMatchesPharmaLens(n.label, pharmaLens)) {
        allowedIds.add(n.id);
      }
    });
    const lensNodes = relationFilteredGraph.nodes.filter((n) => allowedIds.has(n.id));
    const idSet = new Set(lensNodes.map((n) => n.id));
    const lensEdges = relationFilteredGraph.edges.filter((e) => {
      const src = typeof e.source === 'string' ? e.source : e.source.id;
      const dst = typeof e.target === 'string' ? e.target : e.target.id;
      return idSet.has(src) && idSet.has(dst);
    });
    return { nodes: lensNodes, edges: lensEdges };
  }, [relationFilteredGraph, showPharmaGraphUi, pharmaLens]);

  const nodeConnectionMap = useMemo(() => {
    const map = new Map<string, { degree: number; totalWeight: number; relationTypes: Set<string> }>();
    visibleGraph.nodes.forEach((node) => {
      map.set(node.id, { degree: 0, totalWeight: 0, relationTypes: new Set<string>() });
    });
    visibleGraph.edges.forEach((edge) => {
      const src = typeof edge.source === 'string' ? edge.source : edge.source.id;
      const dst = typeof edge.target === 'string' ? edge.target : edge.target.id;
      const entrySrc = map.get(src);
      const entryDst = map.get(dst);
      if (entrySrc) {
        entrySrc.degree += 1;
        entrySrc.totalWeight += Number(edge.weight || 0);
        entrySrc.relationTypes.add(edge.relation);
      }
      if (entryDst) {
        entryDst.degree += 1;
        entryDst.totalWeight += Number(edge.weight || 0);
        entryDst.relationTypes.add(edge.relation);
      }
    });
    return map;
  }, [visibleGraph]);

  const selectedNodeStats = useMemo(() => {
    if (!selectedNode) return null;
    const stats = nodeConnectionMap.get(selectedNode.id);
    if (!stats) return { degree: 0, totalWeight: 0, relationTypes: 0 };
    return {
      degree: stats.degree,
      totalWeight: Number(stats.totalWeight.toFixed(2)),
      relationTypes: stats.relationTypes.size,
    };
  }, [selectedNode, nodeConnectionMap]);

  const applyZoom = (factor: number) => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(220).call(zoomBehaviorRef.current.scaleBy, factor);
  };

  const resetZoom = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(240).call(zoomBehaviorRef.current.transform, d3.zoomIdentity);
  };

  const startRename = () => {
    setRenameError(null);
    setRenameValue((fabricDetails?.name || fabricName || '').trim());
    setIsRenaming(true);
  };

  const cancelRename = () => {
    setIsRenaming(false);
    setRenameError(null);
    setRenameValue('');
  };

  const saveRename = async () => {
    if (!fabricId) return;
    const nextName = renameValue.trim();
    if (!nextName) {
      setRenameError('Fabric name cannot be empty.');
      return;
    }
    try {
      setRenameSaving(true);
      setRenameError(null);
      const response = await apiRequest(`api/v1/knowledge/${fabricId}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nextName }),
      });
      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || payload?.message || `Failed with status ${response.status}`);
      }
      const updatedName = payload?.data?.name || nextName;
      setFabricName(updatedName);
      setFabricDetails((prev) => (prev ? { ...prev, name: updatedName, updated_at: payload?.data?.updated_at ?? prev.updated_at } : prev));
      setIsRenaming(false);
      setRenameValue('');
    } catch (err: any) {
      setRenameError(err?.message || 'Failed to rename fabric');
    } finally {
      setRenameSaving(false);
    }
  };

  const startGuardrailsEdit = () => {
    const current = fabricDetails?.guardrails;
    setGuardrailsError(null);
    setGuardrailsForm({
      data_classification: (current?.data_classification as FabricGuardrails['data_classification']) || 'internal',
      compliance_tags: current?.compliance_tags || [],
      pii_fields: current?.pii_fields || [],
      enforce_masking: current?.enforce_masking ?? true,
      encryption_at_rest: current?.encryption_at_rest ?? true,
      encryption_in_transit: current?.encryption_in_transit ?? true,
      row_level_security: current?.row_level_security ?? false,
      approved_roles: current?.approved_roles || [],
    });
    setIsEditingGuardrails(true);
  };

  const saveGuardrails = async () => {
    if (!fabricId) return;
    try {
      setGuardrailsSaving(true);
      setGuardrailsError(null);
      const response = await apiRequest(`api/v1/knowledge/${fabricId}/guardrails`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guardrails: guardrailsForm }),
      });
      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || payload?.message || `Failed with status ${response.status}`);
      }
      setFabricDetails(payload.data || null);
      setIsEditingGuardrails(false);
    } catch (err: any) {
      setGuardrailsError(err?.message || 'Failed to update guardrails');
    } finally {
      setGuardrailsSaving(false);
    }
  };

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = 1280;
    const height = 760;
    svg.attr('viewBox', `0 0 ${width} ${height}`);
    svg.style('background', 'radial-gradient(circle at 20% 20%, #1f2937 0%, #0b1020 55%, #060913 100%)');

    const defs = svg.append('defs');
    const edgeGlow = defs.append('filter').attr('id', 'edge-glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    edgeGlow.append('feGaussianBlur').attr('stdDeviation', 1.8).attr('result', 'blur');
    edgeGlow.append('feMerge').selectAll('feMergeNode').data(['blur', 'SourceGraphic']).join('feMergeNode').attr('in', (d) => d);
    const nodeShadow = defs.append('filter').attr('id', 'node-shadow').attr('x', '-60%').attr('y', '-60%').attr('width', '220%').attr('height', '220%');
    nodeShadow.append('feDropShadow').attr('dx', 0).attr('dy', 2).attr('stdDeviation', 2).attr('flood-color', '#020617').attr('flood-opacity', 0.7);
    const pulseGlow = defs.append('filter').attr('id', 'pulse-glow').attr('x', '-90%').attr('y', '-90%').attr('width', '280%').attr('height', '280%');
    pulseGlow.append('feDropShadow').attr('dx', 0).attr('dy', 0).attr('stdDeviation', 5.2).attr('flood-color', '#67e8f9').attr('flood-opacity', 0.95);
    const entityGradient = defs.append('radialGradient').attr('id', 'entity-gradient');
    entityGradient.append('stop').attr('offset', '0%').attr('stop-color', '#a5f3fc');
    entityGradient.append('stop').attr('offset', '65%').attr('stop-color', '#22d3ee');
    entityGradient.append('stop').attr('offset', '100%').attr('stop-color', '#0891b2');
    const fabricGradient = defs.append('radialGradient').attr('id', 'fabric-gradient');
    fabricGradient.append('stop').attr('offset', '0%').attr('stop-color', '#fde68a');
    fabricGradient.append('stop').attr('offset', '65%').attr('stop-color', '#f59e0b');
    fabricGradient.append('stop').attr('offset', '100%').attr('stop-color', '#b45309');
    const collectionGradient = defs.append('radialGradient').attr('id', 'collection-gradient');
    collectionGradient.append('stop').attr('offset', '0%').attr('stop-color', '#6ee7b7');
    collectionGradient.append('stop').attr('offset', '100%').attr('stop-color', '#059669');
    const classGradient = defs.append('radialGradient').attr('id', 'class-gradient');
    classGradient.append('stop').attr('offset', '0%').attr('stop-color', '#c4b5fd');
    classGradient.append('stop').attr('offset', '100%').attr('stop-color', '#7c3aed');

    const root = svg.append('g');
    rootGroupRef.current = root;
    const zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 3.4])
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
        setZoomLevel(Number(event.transform.k.toFixed(2)));
      });
    zoomBehaviorRef.current = zoomBehavior;
    svg.call(zoomBehavior);

    const simulation = d3
      .forceSimulation<GraphNode>(visibleGraph.nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(visibleGraph.edges)
          .id((d) => d.id)
          .distance((d) => (d.relation === 'mentions' ? 105 : 70))
      )
      .force('charge', d3.forceManyBody().strength(-270))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<GraphNode>().radius((d) => {
        if (d.type === 'fabric') return 30;
        if (d.type === 'collection' || d.type === 'class') return 18;
        return 12 + Math.min(d.weight, 8);
      }));

    const link = root
      .append('g')
      .attr('stroke-opacity', 0.75)
      .attr('filter', 'url(#edge-glow)')
      .selectAll('line')
      .data(visibleGraph.edges)
      .join('line')
      .attr('stroke', (d) => {
        if (d.relation === 'mentions') return '#22d3ee';
        if (d.relation === 'related_to') return '#c084fc';
        if (d.relation === 'references' || d.relation === 'contains' || d.relation === 'includes') return '#34d399';
        return '#fbbf24';
      })
      .attr('stroke-width', (d) => {
        if (d.relation === 'mentions') return Math.max(1.1, Math.min(3.2, d.weight * 0.25));
        if (d.relation === 'related_to') return Math.max(1.2, Math.min(3.6, d.weight * 0.3));
        return 2.4;
      })
      .attr('stroke-linecap', 'round')
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedEdge(d);
        setSelectedNode(null);
      });

    const linkDirection = root
      .append('g')
      .selectAll('circle')
      .data(visibleGraph.edges)
      .join('circle')
      .attr('r', 2.3)
      .attr('fill', '#e2e8f0')
      .attr('opacity', 0.75);

    const dragBehavior = d3
      .drag<SVGCircleElement, GraphNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    const node = root
      .append('g')
      .selectAll<SVGCircleElement, GraphNode>('circle')
      .data(visibleGraph.nodes)
      .join('circle')
      .attr('r', (d) => {
        if (d.type === 'fabric') return 18;
        if (d.type === 'collection' || d.type === 'class') return Math.max(10, Math.min(16, 8 + Math.log10(Math.max(d.weight, 1)) * 4));
        return Math.max(6, Math.min(12, 5 + Math.min(d.weight, 8) * 0.35));
      })
      .attr('fill', (d) => {
        if (searchTerm.trim() && d.label.toLowerCase().includes(searchTerm.toLowerCase())) return '#f43f5e';
        if (d.type === 'fabric') return 'url(#fabric-gradient)';
        if (d.type === 'collection') return 'url(#collection-gradient)';
        if (d.type === 'class') return 'url(#class-gradient)';
        return 'url(#entity-gradient)';
      })
      .attr('stroke', '#e2e8f0')
      .attr('stroke-width', 1.2)
      .attr('filter', 'url(#node-shadow)')
      .on('click', (_, d) => {
        setSelectedNode(d);
        setSelectedEdge(null);
      })
      .call(dragBehavior);

    const pulseNode = root
      .append('g')
      .attr('pointer-events', 'none')
      .append('circle')
      .attr('fill', 'none')
      .attr('stroke', '#67e8f9')
      .attr('stroke-width', 1.4)
      .attr('opacity', 0.92)
      .attr('filter', 'url(#pulse-glow)');

    const runPulse = () => {
      pulseNode
        .attr('r', 10)
        .attr('stroke-opacity', 0.95)
        .transition()
        .duration(1200)
        .ease(d3.easeCubicOut)
        .attr('r', 28)
        .attr('stroke-opacity', 0)
        .on('end', runPulse);
    };
    runPulse();

    node.append('title').text((d) => `${d.label} (${d.type})`);

    const labels = root
      .append('g')
      .selectAll('text')
      .data(visibleGraph.nodes)
      .join('text')
      .text((d) => d.label)
      .attr('font-size', (d) => (d.type === 'fabric' || d.type === 'collection' || d.type === 'class' ? 12 : 10))
      .attr('font-weight', (d) => (d.type === 'fabric' || d.type === 'collection' || d.type === 'class' ? 700 : 400))
      .attr('fill', '#f8fafc')
      .attr('pointer-events', 'none');

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as GraphNode).x || 0)
        .attr('y1', (d) => (d.source as GraphNode).y || 0)
        .attr('x2', (d) => (d.target as GraphNode).x || 0)
        .attr('y2', (d) => (d.target as GraphNode).y || 0)
        .attr('stroke-opacity', (d) => {
          const sx = (d.source as GraphNode).x || 0;
          const sy = (d.source as GraphNode).y || 0;
          const tx = (d.target as GraphNode).x || 0;
          const ty = (d.target as GraphNode).y || 0;
          const length = Math.hypot(tx - sx, ty - sy);
          const depthFade = Math.max(0.28, 1 - length / 380);
          return Number(depthFade.toFixed(3));
        });
      linkDirection
        .attr('cx', (d) => {
          const sx = (d.source as GraphNode).x || 0;
          const tx = (d.target as GraphNode).x || 0;
          return sx + (tx - sx) * 0.7;
        })
        .attr('cy', (d) => {
          const sy = (d.source as GraphNode).y || 0;
          const ty = (d.target as GraphNode).y || 0;
          return sy + (ty - sy) * 0.7;
        });
      node.attr('cx', (d) => d.x || 0).attr('cy', (d) => d.y || 0);
      const selected = selectedNode && visibleGraph.nodes.find((n) => n.id === selectedNode.id);
      if (selected) {
        pulseNode
          .attr('display', null)
          .attr('cx', selected.x || 0)
          .attr('cy', selected.y || 0);
      } else {
        pulseNode.attr('display', 'none');
      }
      labels.attr('x', (d) => (d.x || 0) + 8).attr('y', (d) => (d.y || 0) + 4);
    });

    return () => {
      pulseNode.interrupt();
      simulation.stop();
    };
  }, [visibleGraph, searchTerm, selectedNode]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Knowledge Graph</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
                graphType === 'canonical' || graphType === 'profiled_schema'
                  ? 'border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b]'
                  : graphType === 'stale_schema' || graphType === 'exploratory'
                  ? 'border-[rgba(232,184,74,0.4)] bg-[rgba(232,184,74,0.12)] text-[#e8b84a]'
                  : 'border-[rgba(148,163,184,0.25)] bg-white/[0.05] text-[#8b9cb0]'
              }`}
            >
              {GRAPH_TYPE_LABELS[graphType] || graphType}
            </span>
            {ontologyVersionId && (
              <span className="text-[11px] text-[#8b9cb0] font-mono">v {ontologyVersionId}</span>
            )}
          </div>
          {!isRenaming ? (
            <div className="mt-1 flex items-center gap-2">
              <p className="text-gray-600">{fabricName}</p>
              <button
                type="button"
                onClick={startRename}
                className="rounded-md border border-[rgba(148,163,184,0.25)] bg-white/[0.05] px-2 py-1 text-[11px] text-[#cbd5e1] hover:bg-white/[0.08]"
              >
                Rename
              </button>
              <button
                type="button"
                onClick={startGuardrailsEdit}
                className="rounded-md border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.16)] px-2 py-1 text-[11px] text-[#cfefff] hover:bg-[rgba(94,200,242,0.24)]"
              >
                Edit Guardrails
              </button>
            </div>
          ) : (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <input
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                maxLength={120}
                className="w-[320px] max-w-full rounded-lg border border-[rgba(148,163,184,0.25)] bg-[#10141d]/80 px-3 py-1.5 text-sm"
                placeholder="Enter fabric name"
              />
              <button
                type="button"
                onClick={saveRename}
                disabled={renameSaving}
                className="rounded-md border border-[rgba(62,207,155,0.4)] bg-[rgba(62,207,155,0.18)] px-2 py-1 text-[11px] text-[#9af0ca] disabled:opacity-50"
              >
                {renameSaving ? 'Saving...' : 'Save'}
              </button>
              <button
                type="button"
                onClick={cancelRename}
                disabled={renameSaving}
                className="rounded-md border border-[rgba(148,163,184,0.25)] bg-white/[0.05] px-2 py-1 text-[11px] text-[#cbd5e1] disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          )}
          {renameError && <p className="mt-1 text-xs text-[#fca5a5]">{renameError}</p>}
          {guardrailsError && <p className="mt-1 text-xs text-[#fca5a5]">{guardrailsError}</p>}
        </div>
        <Link to="/fabrics" className="px-4 py-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#cbd5e1] hover:bg-white/[0.05]">
          Back to Fabrics
        </Link>
      </div>

      {loading && <p className="text-gray-600">Building graph from fabric data...</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && !error && fabricId && (
        <FabricPlatformPanel
          fabricId={fabricId}
          ontologyProjectId={fabricDetails?.ontology_project_id}
          approvedOntologyVersionId={ontologyVersionId || fabricDetails?.approved_ontology_version_id}
          onGraphUpdated={() => setGraphReloadKey((k) => k + 1)}
        />
      )}

      {!loading && !error && (
        <>
          {availableViews.length > 0 && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-[0.14em] text-[#8b9cb0] mr-1">View</span>
              {availableViews.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setActiveView(v.id)}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    activeView === v.id
                      ? 'border-[rgba(94,200,242,0.45)] bg-[rgba(94,200,242,0.18)] text-[#cfefff]'
                      : 'border-[rgba(148,163,184,0.25)] bg-white/[0.03] text-[#8b9cb0] hover:bg-white/[0.06]'
                  }`}
                >
                  {v.label}
                  {v.node_count != null ? ` · ${v.node_count}` : ''}
                </button>
              ))}
            </div>
          )}

          {graphNote && (
            <div className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
              rebuildRequired
                ? 'border-[rgba(232,184,74,0.4)] bg-[rgba(232,184,74,0.1)] text-[#f5d78e]'
                : 'border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.08)] text-[#cbd5e1]'
            }`}>
              <p className="font-semibold text-[#e8edf4] mb-1">How this graph was built</p>
              <p>{graphNote}</p>
              {sampleMeta.capped && sampleMeta.size != null && sampleMeta.total != null && (
                <p className="mt-1 text-xs text-[#8b9cb0]">
                  Sample on canvas: {sampleMeta.size.toLocaleString()} of {sampleMeta.total.toLocaleString()} rows/chunks.
                </p>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Nodes</p>
              <p className="text-2xl font-semibold text-gray-900">{graphStats.nodes}</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">
                {graphStats.collections ? 'Tables' : graphStats.classes ? 'Classes' : 'Entities'}
              </p>
              <p className="text-2xl font-semibold text-gray-900">
                {graphStats.collections || graphStats.classes || graphStats.entities}
              </p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Relationships</p>
              <p className="text-2xl font-semibold text-gray-900">{graphStats.edges}</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Density</p>
              <p className="text-2xl font-semibold text-gray-900">{analytics?.graph_density ?? 0}</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Source Type</p>
              <p className="text-2xl font-semibold text-gray-900">{fabricDetails?.source_type || '-'}</p>
            </div>
          </div>

          {fabricDetails?.source_type === 'codebase' && fabricId && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.1)] px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-[#e8edf4]">Migration package</p>
                <p className="text-xs text-[#8b9cb0]">
                  Download the full migration JSON (inventory, graph, blueprint, risks).
                </p>
              </div>
              <button
                type="button"
                onClick={async () => {
                  try {
                    const response = await authenticatedFetch(
                      getApiUrl(`api/v1/knowledge/${fabricId}/migration-export`)
                    );
                    if (!response.ok) {
                      throw new Error(`Download failed (${response.status})`);
                    }
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `fabric_${fabricId}_migration.json`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                  } catch (err) {
                    alert(err instanceof Error ? err.message : 'Download failed');
                  }
                }}
                className="rounded-lg border border-[rgba(62,207,155,0.45)] bg-[rgba(62,207,155,0.2)] px-4 py-2 text-sm font-medium text-[#9af0ca] hover:bg-[rgba(62,207,155,0.3)]"
              >
                Download migration JSON
              </button>
            </div>
          )}

          {fabricDetails?.source_type === 'codebase' && (
            <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.08)] p-4">
                <p className="text-sm font-semibold text-[#e8edf4] mb-2">Discovery summary</p>
                <p className="text-sm text-[#cbd5e1] whitespace-pre-wrap">
                  {fabricDetails.discovery_summary || 'No discovery summary yet.'}
                </p>
              </div>
              <div className="rounded-xl border border-[rgba(62,207,155,0.3)] bg-[rgba(62,207,155,0.08)] p-4">
                <p className="text-sm font-semibold text-[#e8edf4] mb-2">Migration blueprint</p>
                <p className="text-sm text-[#cbd5e1] mb-3">
                  {fabricDetails.migration_blueprint?.narrative || 'No blueprint narrative yet.'}
                </p>
                <div className="space-y-2">
                  {(fabricDetails.migration_blueprint?.waves || []).slice(0, 4).map((wave, idx) => (
                    <div key={idx} className="rounded-lg border border-[rgba(148,163,184,0.15)] bg-white/[0.03] px-3 py-2">
                      <p className="text-xs font-semibold text-[#d9f4ff]">{wave.name || `Wave ${idx + 1}`}</p>
                      <p className="text-[11px] text-[#8b9cb0]">{wave.intent}</p>
                      <p className="text-[11px] text-[#cbd5e1] mt-1">
                        {(wave.modules || []).slice(0, 8).join(', ') || '—'}
                      </p>
                    </div>
                  ))}
                </div>
                {(fabricDetails.migration_blueprint?.risks || []).length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-[#8b9cb0] mb-1">Top risks</p>
                    <ul className="space-y-1">
                      {(fabricDetails.migration_blueprint?.risks || []).slice(0, 5).map((risk, idx) => (
                        <li key={idx} className="text-xs text-[#f08984]">
                          [{risk.severity || 'risk'}] {risk.message || risk.type}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {fabricDetails?.guardrails && (
            <div className="mb-4 rounded-xl border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.08)] p-4">
              <p className="text-sm font-semibold text-[#e8edf4] mb-2">Guardrails</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs text-[#cbd5e1]">
                <div>
                  <p className="text-[#8b9cb0]">Classification</p>
                  <p className="font-semibold text-[#e8edf4]">{fabricDetails.guardrails.data_classification || 'internal'}</p>
                </div>
                <div>
                  <p className="text-[#8b9cb0]">Compliance</p>
                  <p className="font-semibold text-[#e8edf4]">{(fabricDetails.guardrails.compliance_tags || []).join(', ') || '-'}</p>
                </div>
                <div>
                  <p className="text-[#8b9cb0]">PII fields</p>
                  <p className="font-semibold text-[#e8edf4]">{(fabricDetails.guardrails.pii_fields || []).join(', ') || '-'}</p>
                </div>
                <div>
                  <p className="text-[#8b9cb0]">Approved roles</p>
                  <p className="font-semibold text-[#e8edf4]">{(fabricDetails.guardrails.approved_roles || []).join(', ') || '-'}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-[rgba(148,163,184,0.25)] px-2 py-1">
                  Masking: {fabricDetails.guardrails.enforce_masking ? 'On' : 'Off'}
                </span>
                <span className="rounded-full border border-[rgba(148,163,184,0.25)] px-2 py-1">
                  Encryption(rest): {fabricDetails.guardrails.encryption_at_rest ? 'On' : 'Off'}
                </span>
                <span className="rounded-full border border-[rgba(148,163,184,0.25)] px-2 py-1">
                  Encryption(transit): {fabricDetails.guardrails.encryption_in_transit ? 'On' : 'Off'}
                </span>
                <span className="rounded-full border border-[rgba(148,163,184,0.25)] px-2 py-1">
                  RLS: {fabricDetails.guardrails.row_level_security ? 'On' : 'Off'}
                </span>
              </div>
            </div>
          )}

          {isEditingGuardrails && (
            <div className="mb-4 rounded-xl border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.08)] p-4">
              <p className="text-sm font-semibold text-[#e8edf4] mb-3">Edit Guardrails</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
                <label className="text-xs text-[#8b9cb0]">
                  Classification
                  <select
                    value={guardrailsForm.data_classification}
                    onChange={(e) =>
                      setGuardrailsForm((prev) => ({
                        ...prev,
                        data_classification: e.target.value as FabricGuardrails['data_classification'],
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                  >
                    <option value="public">Public</option>
                    <option value="internal">Internal</option>
                    <option value="confidential">Confidential</option>
                    <option value="restricted">Restricted</option>
                  </select>
                </label>
                <label className="text-xs text-[#8b9cb0]">
                  Compliance tags
                  <input
                    value={guardrailsForm.compliance_tags.join(', ')}
                    onChange={(e) =>
                      setGuardrailsForm((prev) => ({
                        ...prev,
                        compliance_tags: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                    placeholder="HIPAA, SOC2"
                  />
                </label>
                <label className="text-xs text-[#8b9cb0]">
                  PII fields
                  <input
                    value={guardrailsForm.pii_fields.join(', ')}
                    onChange={(e) =>
                      setGuardrailsForm((prev) => ({
                        ...prev,
                        pii_fields: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                    placeholder="email, phone"
                  />
                </label>
                <label className="text-xs text-[#8b9cb0]">
                  Approved roles
                  <input
                    value={guardrailsForm.approved_roles.join(', ')}
                    onChange={(e) =>
                      setGuardrailsForm((prev) => ({
                        ...prev,
                        approved_roles: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                    placeholder="admin, auditor"
                  />
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-[#cbd5e1]">
                <label><input type="checkbox" checked={guardrailsForm.enforce_masking} onChange={() => setGuardrailsForm((p) => ({ ...p, enforce_masking: !p.enforce_masking }))} /> <span className="ml-1">Masking</span></label>
                <label><input type="checkbox" checked={guardrailsForm.encryption_at_rest} onChange={() => setGuardrailsForm((p) => ({ ...p, encryption_at_rest: !p.encryption_at_rest }))} /> <span className="ml-1">Encrypt at rest</span></label>
                <label><input type="checkbox" checked={guardrailsForm.encryption_in_transit} onChange={() => setGuardrailsForm((p) => ({ ...p, encryption_in_transit: !p.encryption_in_transit }))} /> <span className="ml-1">Encrypt in transit</span></label>
                <label><input type="checkbox" checked={guardrailsForm.row_level_security} onChange={() => setGuardrailsForm((p) => ({ ...p, row_level_security: !p.row_level_security }))} /> <span className="ml-1">RLS</span></label>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  onClick={saveGuardrails}
                  disabled={guardrailsSaving}
                  className="rounded-md border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.16)] px-3 py-1.5 text-xs text-[#bdf5dd] disabled:opacity-50"
                >
                  {guardrailsSaving ? 'Saving...' : 'Save Guardrails'}
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditingGuardrails(false)}
                  disabled={guardrailsSaving}
                  className="rounded-md border border-[rgba(148,163,184,0.25)] bg-white/[0.05] px-3 py-1.5 text-xs text-[#cbd5e1] disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {showPharmaGraphUi && (
            <div className="mb-4 rounded-xl border border-[rgba(155,139,212,0.35)] bg-[rgba(155,139,212,0.09)] p-4">
              <div className="flex flex-col lg:flex-row lg:items-start gap-4 justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900">Pharma knowledge graph views</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Same graph canvas—switch lenses to emphasize drug product, lineage, experiments, process, quality, deviations, or SOP coverage.
                  </p>
                  <p className="text-[11px] text-[#64748b] mt-2">
                    Nodes may represent Drug Product, API, Excipient, Formulation, Batch, Lot, Experiment, Manufacturing Step, Equipment, Process Parameter,
                    CQA, Analytical Test, Deviation, CAPA, SOP, Protocol—as surfaced from your fabric.
                  </p>
                </div>
                <div className="w-full lg:w-72 shrink-0">
                  <label className="block text-xs font-medium text-gray-600 mb-1">Lens</label>
                  <select
                    value={pharmaLens}
                    onChange={(e) => setPharmaLens(e.target.value as PharmaGraphLens)}
                    className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 bg-[#10141d]/70 text-[#e8edf4] border-[rgba(148,163,184,0.25)]"
                  >
                    {PHARMA_GRAPH_VIEWS.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-gray-500 mt-1.5">{PHARMA_GRAPH_VIEWS.find((x) => x.id === pharmaLens)?.hint}</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] text-gray-600">
                <div className="rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-3">
                  <p className="font-semibold text-gray-800 mb-1">Example relationships</p>
                  <ul className="list-disc pl-4 space-y-0.5">
                    <li>batch produced using equipment</li>
                    <li>experiment tests formulation</li>
                    <li>process step has parameter</li>
                    <li>test measures CQA</li>
                    <li>deviation impacts batch</li>
                    <li>SOP governs process step</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-3">
                  <p className="font-semibold text-gray-800 mb-1">Weave domain</p>
                  <p className="text-[#cbd5e1]">
                    {fabricDetails?.weave_domain === 'pharma' || (fabricDetails?.tags || []).some((t) => /pharma|weave:pharma/i.test(t))
                      ? 'Pharma Drug Manufacturing (tagged fabric)'
                      : 'Session set to pharma — showing pharma overlays'}
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {graphType === 'exploratory' ? (
                <>
                  <div className="flex items-center gap-2">
                    <input id="mentions" type="checkbox" checked={showMentions} onChange={(e) => setShowMentions(e.target.checked)} />
                    <label htmlFor="mentions" className="text-sm text-gray-700">Show `mentions`</label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input id="related" type="checkbox" checked={showRelated} onChange={(e) => setShowRelated(e.target.checked)} />
                    <label htmlFor="related" className="text-sm text-gray-700">Show `related_to`</label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input id="other-relations" type="checkbox" checked={showOtherRelations} onChange={(e) => setShowOtherRelations(e.target.checked)} />
                    <label htmlFor="other-relations" className="text-sm text-gray-700">Show other relations</label>
                  </div>
                </>
              ) : (
                <div className="md:col-span-3 text-sm text-gray-600">
                  {graphType === 'canonical'
                    ? 'Ontology class relationships (approved). Switch to Data view for measured tables and sample rows.'
                    : graphType === 'profiled_schema'
                    ? 'Tables, foreign keys measured by value overlap, and sample instance rows from the table store.'
                    : graphType === 'stale_schema'
                    ? 'Rebuild this fabric to unlock measured foreign keys and sample instances.'
                    : 'Structured relationships for this fabric.'}
                </div>
              )}
              <div>
                <input
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search entity..."
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2"
                />
              </div>
              <div>
                <select
                  value={focusHops}
                  onChange={(e) => setFocusHops(Number(e.target.value) as 0 | 1 | 2)}
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2"
                >
                  <option value={0}>Focus: Off</option>
                  <option value={1}>Focus: 1-hop from selected</option>
                  <option value={2}>Focus: 2-hop from selected</option>
                </select>
              </div>
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[28px] border border-white/15 bg-[#070b12] p-2 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
            <svg ref={svgRef} className="w-full h-[72vh] min-h-[560px] max-h-[820px]" />

            <div className="absolute top-3 left-3 rounded-xl p-3 border border-cyan-300/20 bg-gradient-to-br from-slate-950/95 via-slate-900/92 to-cyan-950/90 backdrop-blur-xl shadow-lg shadow-cyan-950/35 w-[250px]">
              <h3 className="text-xs font-semibold text-white mb-1">Fabric Details</h3>
              <p className="text-xs text-slate-100/90">Weave domain: <span className="font-semibold text-violet-200">{fabricDetails?.weave_domain || 'generic'}</span></p>
              <p className="text-xs text-slate-100/90">Status: <span className="font-semibold text-cyan-200">{fabricDetails?.status || '-'}</span></p>
              <p className="text-xs text-slate-100/90">Model: <span className="font-semibold text-fuchsia-200">{fabricDetails?.model_status || '-'}</span></p>
              <p className="text-xs text-slate-100/90">Documents: <span className="font-semibold text-emerald-200">{fabricDetails?.document_count ?? 0}</span></p>
              <p className="text-xs text-slate-100/90">Chunks: <span className="font-semibold text-amber-200">{fabricDetails?.total_chunks ?? 0}</span></p>
            </div>

            <div className="absolute top-3 right-3 rounded-xl border border-[rgba(148,163,184,0.25)] bg-[#0b0f16]/92 backdrop-blur px-2 py-2">
              <div className="text-[11px] text-[#8b9cb0] mb-1">Zoom {zoomLevel.toFixed(2)}x</div>
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => applyZoom(0.82)} className="h-8 w-8 rounded border border-[rgba(148,163,184,0.2)] text-sm text-[#cbd5e1] hover:bg-white/[0.08]">-</button>
                <button type="button" onClick={() => applyZoom(1.2)} className="h-8 w-8 rounded border border-[rgba(148,163,184,0.2)] text-sm text-[#cbd5e1] hover:bg-white/[0.08]">+</button>
                <button type="button" onClick={resetZoom} className="h-8 px-2 rounded border border-[rgba(148,163,184,0.2)] text-[11px] text-[#cbd5e1] hover:bg-white/[0.08]">Reset</button>
              </div>
            </div>

            <div className="absolute top-3 left-1/2 -translate-x-1/2 rounded-lg border border-[rgba(148,163,184,0.22)] bg-[#0b0f16]/88 backdrop-blur px-3 py-2 flex flex-wrap items-center gap-3 text-[11px] text-[#9fb0c5] max-w-[90%]">
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Fabric</span>
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Table</span>
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-cyan-300" /> Instance</span>
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-violet-400" /> Ontology class</span>
              <span className="inline-flex items-center gap-1"><span className="h-0.5 w-5 bg-emerald-400" /> references</span>
              <span className="inline-flex items-center gap-1"><span className="h-0.5 w-5 bg-cyan-400" /> mentions</span>
              <span className="inline-flex items-center gap-1"><span className="h-0.5 w-5 bg-fuchsia-400" /> related_to</span>
            </div>

            {visibleGraph.nodes.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="rounded-lg border border-[rgba(148,163,184,0.22)] bg-[#0b0f16]/90 px-4 py-2 text-sm text-[#9fb0c5]">
                  No nodes visible with current filters. Adjust relation filters or focus hops.
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
            <section className="relative overflow-hidden rounded-[24px] border border-white/15 bg-white/[0.07] p-4 shadow-[0_16px_50px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.22)] backdrop-blur-2xl lg:col-span-5">
              <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent" />
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">Brief</p>
                <span className="rounded-full border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)] px-2 py-0.5 text-[10px] text-[#9adfff]">Live</span>
              </div>
              <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-[#e8edf4]">Key Insights</h3>
              <div className="mt-3 max-h-[320px] overflow-auto text-[13px] leading-relaxed text-[#d5deea]">
                {renderLlmGraphInsight(llmInsight?.summary || 'No insight available yet.')}
              </div>
            </section>

            <section className="relative overflow-hidden rounded-[24px] border border-white/15 bg-white/[0.07] p-4 shadow-[0_16px_50px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.22)] backdrop-blur-2xl lg:col-span-3">
              <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent" />
              <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">Weight</p>
              <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-[#e8edf4]">Top Entities</h3>
              <div className="mt-3 max-h-[320px] space-y-1.5 overflow-auto">
                {(analytics?.top_entities || []).length === 0 && (
                  <p className="text-[12px] text-[#8b9cb0]">Entities appear after the graph is published.</p>
                )}
                {(analytics?.top_entities || []).map((entity) => (
                  <div key={entity.label} className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-1.5">
                    <span className="truncate text-[12px] text-[#e8edf4]">{entity.label}</span>
                    <span className="shrink-0 text-[12px] font-semibold tabular-nums text-[#d7cff5]">{entity.weight}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="relative overflow-hidden rounded-[24px] border border-white/15 bg-white/[0.07] p-4 shadow-[0_16px_50px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.22)] backdrop-blur-2xl lg:col-span-4">
              <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent" />
              <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">Selection</p>
              <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-[#e8edf4]">Inspector</h3>
              <div className="mt-3 max-h-[320px] overflow-auto text-[12px] leading-relaxed text-[#d5deea]">
                {selectedNode ? (
                  <>
                    <p>Label: <span className="font-semibold text-[#9adfff]">{selectedNode.label}</span></p>
                    <p>Type: <span className="font-semibold text-[#9af0ca]">{selectedNode.type}</span></p>
                    {selectedNode.group && (
                      <p>Group: <span className="font-semibold text-[#f3d48a]">{selectedNode.group}</span></p>
                    )}
                    <p>Connections: <span className="font-semibold text-[#d7cff5]">{selectedNodeStats?.degree ?? 0}</span></p>
                    {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                      <div className="mt-2 space-y-1 border-t border-white/10 pt-2">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Properties</p>
                        {Object.entries(selectedNode.properties).map(([key, value]) => {
                          if (key === 'fields' && value && typeof value === 'object') {
                            return (
                              <div key={key} className="space-y-0.5">
                                <p className="text-[10px] text-[#8b9cb0]">fields</p>
                                {Object.entries(value as Record<string, unknown>).slice(0, 8).map(([fk, fv]) => (
                                  <p key={fk} className="pl-2"><span className="text-[#8b9cb0]">{fk}:</span> {String(fv)}</p>
                                ))}
                              </div>
                            );
                          }
                          const shown = Array.isArray(value) ? value.join(', ') : typeof value === 'object' ? JSON.stringify(value) : String(value);
                          return (
                            <p key={key} className="break-words"><span className="text-[#8b9cb0]">{key}:</span> {shown.slice(0, 160)}</p>
                          );
                        })}
                      </div>
                    )}
                  </>
                ) : selectedEdge ? (
                  <>
                    <p>Relation: <span className="font-semibold text-[#9adfff]">{selectedEdge.relation}</span></p>
                    <p>
                      From → To:{' '}
                      <span className="font-semibold text-[#9af0ca]">
                        {typeof selectedEdge.source === 'string' ? selectedEdge.source : selectedEdge.source.id}
                        {' → '}
                        {typeof selectedEdge.target === 'string' ? selectedEdge.target : selectedEdge.target.id}
                      </span>
                    </p>
                    {selectedEdge.properties && Object.keys(selectedEdge.properties).length > 0 && (
                      <div className="mt-2 space-y-1 border-t border-white/10 pt-2">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Evidence</p>
                        {selectedEdge.properties.confidence != null && (
                          <p className="text-[#9af0ca]">
                            confidence: <span className="font-semibold">{Number(selectedEdge.properties.confidence).toFixed(3)}</span>
                          </p>
                        )}
                        {selectedEdge.properties.evidence != null && selectedEdge.properties.evidence !== '' && (
                          <p className="break-words"><span className="text-[#8b9cb0]">evidence:</span> {String(selectedEdge.properties.evidence).slice(0, 220)}</p>
                        )}
                        {Object.entries(selectedEdge.properties).map(([key, value]) => {
                          if (value == null || value === '' || key === 'confidence' || key === 'evidence') return null;
                          const shown = Array.isArray(value) ? value.map((v) => (typeof v === 'object' ? JSON.stringify(v) : String(v))).join('; ') : typeof value === 'object' ? JSON.stringify(value) : String(value);
                          return (
                            <p key={key} className="break-words"><span className="text-[#8b9cb0]">{key}:</span> {shown.slice(0, 220)}</p>
                          );
                        })}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-[#8b9cb0]">Click a node or an edge on the canvas. Its properties and evidence show up here.</p>
                )}
              </div>
            </section>
          </div>

          <section className="relative mt-4 overflow-hidden rounded-[28px] border border-white/15 bg-white/[0.06] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.2)] backdrop-blur-2xl">
            <div className="pointer-events-none absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent" />
            <h3 className="text-[18px] font-semibold tracking-[-0.03em] text-[#e8edf4]">How this graph is built</h3>
            <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-[#cbd5e1]">
              Weave reads the fabric and records what is in it. An edge is drawn when it can name the two things being connected, the evidence that tied them together, and how sure that tie is. The six steps below are that path, from the raw source to the canvas in front of you.
            </p>
            <ol className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {[
                ['01 Profile', 'Tables are measured first. Each column gets a type, a null rate, and a check for whether its values could be a key. A link between two tables is kept when the values really overlap, and that overlap becomes the confidence on the edge.'],
                ['02 Parse', 'Documents are read the way they are laid out. Headings, tables, and page numbers stay with the text. A scanned page is read with OCR. Each piece remembers its section and page, so a later citation can point back to the exact place it came from.'],
                ['03 Model', 'Those measurements become the ontology. Entities come from the tables and the sections. Each relationship stores its source, its target, the columns or passage that bind them, and the evidence snippet. Domain rules are applied from the matching pack for this kind of data.'],
                ['04 Index', 'The rows stay in a table store, so a count is answered from the rows themselves. Text and short entity summaries are embedded, and the embedding model is stamped on the fabric. This fabric keeps its own index, separate from every other fabric.'],
                ['05 Validate', 'Search is checked against that index before anything is shown. If the index is not the one just built, the fabric is held back. Counts are checked against the table store. The graph is published when those measurements still hold.'],
                ['06 Publish', 'What you see here is that published graph: the classes, plus a sample of real records, joined by the links found above. Selecting a node opens the values behind it. Selecting an edge opens the evidence and the confidence.'],
              ].map(([title, copy]) => (
                <li key={title} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                  <p className="text-[12px] font-semibold tracking-[-0.01em] text-[#e8edf4]">{title}</p>
                  <p className="mt-1 text-[12px] leading-relaxed text-[#9fb0c5]">{copy}</p>
                </li>
              ))}
            </ol>
            <p className="mt-4 max-w-3xl text-[13px] leading-relaxed text-[#cbd5e1]">
              When a fabric is made from more than one source, the same steps run on the combined profile. A person named in a document is matched to the row that carries the same identity, and both sources share one ontology. A question about a count goes to the table store. A question about what a document says goes to the indexed text. A question that needs both uses the rows and the passages together, and the confidence you see is the confidence measured while the graph was built.
            </p>
          </section>
        </>
      )}
    </div>
  );
};

export default FabricKnowledgeGraph;
