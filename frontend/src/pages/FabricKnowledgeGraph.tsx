import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import * as d3 from 'd3';
import { apiRequest } from '../utils/api';
import { renderLlmGraphInsight } from '../utils/renderLlmGraphInsight';
import FabricPlatformPanel from '../components/FabricPlatformPanel';
import { getWeaveDomain } from '../utils/weaveDomain';
import {
  PHARMA_GRAPH_VIEWS,
  labelMatchesPharmaLens,
  shouldShowPharmaGraphUi,
  type PharmaGraphLens,
} from '../utils/pharmaGraphLens';

type GraphNodeType = 'fabric' | 'entity';

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: GraphNodeType;
  weight: number;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  relation: string;
  weight: number;
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

type GraphViewType = 'canonical' | 'exploratory';

function normalizeGraphPayload(data: Record<string, unknown>): {
  nodes: GraphNode[];
  edges: GraphEdge[];
  graphType: GraphViewType;
  ontologyVersionId?: string;
} {
  const graphType = (data.graph_type as GraphViewType) || 'exploratory';
  const rawNodes = (data.nodes as Array<Record<string, unknown>>) || [];
  const rawEdges = (data.edges as Array<Record<string, unknown>>) || [];

  const nodes: GraphNode[] = rawNodes.map((n) => ({
    id: String(n.id),
    label: String(n.label || n.normalized_name || n.id),
    type: (n.type === 'fabric' ? 'fabric' : 'entity') as GraphNodeType,
    weight: Number(n.weight ?? 1),
  }));

  const edges: GraphEdge[] = rawEdges.map((e) => ({
    source: String(e.source),
    target: String(e.target),
    relation: String(e.relation || e.label || e.relationship_type || 'relates_to'),
    weight: Number(e.weight ?? 1),
  }));

  return {
    nodes,
    edges,
    graphType,
    ontologyVersionId: data.ontology_version_id as string | undefined,
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

  const showPharmaGraphUi = shouldShowPharmaGraphUi(getWeaveDomain(), fabricDetails);

  const loadGraph = useCallback(async () => {
    if (!fabricId) return;
    try {
      setLoading(true);
      setError(null);
      const response = await apiRequest(`api/v1/knowledge/${fabricId}/knowledge-graph?include_llm=true`);
      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.message || `Request failed: ${response.status}`);
      }
      const data = payload.data || {};
      const normalized = normalizeGraphPayload(data);
      setFabricName(String(data.fabric_name || 'Knowledge Fabric'));
      setNodes(normalized.nodes);
      setEdges(normalized.edges);
      setGraphType(normalized.graphType);
      setOntologyVersionId(normalized.ontologyVersionId);
      setAnalytics((data.analytics as GraphAnalytics) || null);
      setLlmInsight((data.llm_insight as LLMInsight) || null);
      setFabricDetails((data.fabric_details as FabricDetails) || null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [fabricId]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph, graphReloadKey]);

  const graphStats = useMemo(
    () => ({
      nodes: nodes.length,
      edges: edges.length,
      entities: nodes.filter((n) => n.type === 'entity').length,
    }),
    [nodes, edges]
  );

  const relationFilteredGraph = useMemo(() => {
    let relationFiltered = edges.filter((e) => {
      if (e.relation === 'mentions') return showMentions;
      if (e.relation === 'related_to') return showRelated;
      return showOtherRelations;
    });

    let nodesAllowed = new Set(nodes.map((n) => n.id));

    if (focusHops > 0 && selectedNode) {
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
      relationFiltered = relationFiltered.filter((e) => {
        const src = typeof e.source === 'string' ? e.source : e.source.id;
        const dst = typeof e.target === 'string' ? e.target : e.target.id;
        return nodesAllowed.has(src) && nodesAllowed.has(dst);
      });
    }

    const nodeFiltered = nodes.filter((n) => nodesAllowed.has(n.id));
    return { nodes: nodeFiltered, edges: relationFiltered };
  }, [nodes, edges, showMentions, showRelated, showOtherRelations, focusHops, selectedNode]);

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
      .force('collision', d3.forceCollide<GraphNode>().radius((d) => (d.type === 'fabric' ? 30 : 12 + Math.min(d.weight, 10))));

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
        return '#fbbf24';
      })
      .attr('stroke-width', (d) => {
        if (d.relation === 'mentions') return Math.max(1.1, Math.min(3.2, d.weight * 0.25));
        if (d.relation === 'related_to') return Math.max(1.2, Math.min(3.6, d.weight * 0.3));
        return 2.4;
      })
      .attr('stroke-linecap', 'round');

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
      .attr('r', (d) => (d.type === 'fabric' ? 18 : Math.max(6, Math.min(13, 5 + d.weight * 0.35))))
      .attr('fill', (d) => {
        if (searchTerm.trim() && d.label.toLowerCase().includes(searchTerm.toLowerCase())) return '#f43f5e';
        if (d.type === 'fabric') return 'url(#fabric-gradient)';
        return 'url(#entity-gradient)';
      })
      .attr('stroke', '#e2e8f0')
      .attr('stroke-width', 1.2)
      .attr('filter', 'url(#node-shadow)')
      .on('click', (_, d) => setSelectedNode(d))
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
      .attr('font-size', (d) => (d.type === 'fabric' ? 12 : 10))
      .attr('font-weight', (d) => (d.type === 'fabric' ? 700 : 400))
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
                graphType === 'canonical'
                  ? 'border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.14)] text-[#3ecf9b]'
                  : 'border-[rgba(148,163,184,0.25)] bg-white/[0.05] text-[#8b9cb0]'
              }`}
            >
              {graphType === 'canonical' ? 'Canonical (approved ontology)' : 'Exploratory (co-occurrence)'}
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
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Nodes</p>
              <p className="text-2xl font-semibold text-gray-900">{graphStats.nodes}</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Entities</p>
              <p className="text-2xl font-semibold text-gray-900">{graphStats.entities}</p>
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
                  Schema relationships from approved ontology. Use the platform panel above to rebuild after approval.
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

          <div className="bg-white border border-gray-200 rounded-xl p-2 relative overflow-hidden">
            <svg ref={svgRef} className="w-full h-[68vh] min-h-[520px] max-h-[760px]" />

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
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-cyan-300" /> Entity</span>
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Fabric</span>
              <span className="inline-flex items-center gap-1"><span className="h-0.5 w-5 bg-cyan-400" /> mentions</span>
              <span className="inline-flex items-center gap-1"><span className="h-0.5 w-5 bg-fuchsia-400" /> related_to</span>
              <span className="inline-flex items-center gap-1"><span className="h-0.5 w-5 bg-amber-300" /> other</span>
            </div>

            <div className="absolute top-24 right-3 rounded-xl p-3 border border-fuchsia-300/20 bg-gradient-to-br from-slate-950/95 via-indigo-950/92 to-fuchsia-950/90 backdrop-blur-xl shadow-lg shadow-indigo-950/35 w-[270px] max-h-[230px] overflow-auto">
              <h3 className="text-xs font-semibold text-white mb-1">Top Entities</h3>
              <div className="space-y-1">
                {(analytics?.top_entities || []).map((entity) => (
                  <div key={entity.label} className="flex justify-between text-xs text-slate-100/95">
                    <span className="truncate pr-2">{entity.label}</span>
                    <span className="font-semibold text-fuchsia-200">{entity.weight}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="absolute bottom-3 left-3 rounded-xl p-3 border border-emerald-300/20 bg-gradient-to-br from-slate-950/95 via-emerald-950/92 to-cyan-950/90 backdrop-blur-xl shadow-lg shadow-emerald-950/35 w-[300px]">
              <h3 className="text-xs font-semibold text-white mb-1">Node Inspector</h3>
              {selectedNode ? (
                <>
                  <p className="text-xs text-slate-100/90">Label: <span className="font-semibold text-cyan-200">{selectedNode.label}</span></p>
                  <p className="text-xs text-slate-100/90">Type: <span className="font-semibold text-emerald-200">{selectedNode.type}</span></p>
                  <p className="text-xs text-slate-100/90">Weight: <span className="font-semibold text-amber-200">{selectedNode.weight}</span></p>
                  <p className="text-xs text-slate-100/90">Connections: <span className="font-semibold text-fuchsia-200">{selectedNodeStats?.degree ?? 0}</span></p>
                  <p className="text-xs text-slate-100/90">Relation Types: <span className="font-semibold text-cyan-200">{selectedNodeStats?.relationTypes ?? 0}</span></p>
                  <p className="text-xs text-slate-100/90">Signal Weight: <span className="font-semibold text-emerald-200">{selectedNodeStats?.totalWeight ?? 0}</span></p>
                </>
              ) : (
                <p className="text-xs text-slate-100/80">Click a node to inspect.</p>
              )}
            </div>

            <div className="absolute bottom-3 right-3 rounded-xl p-3 border border-cyan-400/30 bg-gradient-to-br from-slate-900/95 via-indigo-900/95 to-slate-900/95 shadow-lg shadow-indigo-900/20 w-[340px] max-h-[230px] overflow-auto">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-white">LLM Insight</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-200 border border-cyan-400/30">Brief</span>
              </div>
              <div className="text-slate-100 antialiased selection:bg-cyan-500/20">
                {renderLlmGraphInsight(llmInsight?.summary || 'No insight available.')}
              </div>
            </div>

            {visibleGraph.nodes.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="rounded-lg border border-[rgba(148,163,184,0.22)] bg-[#0b0f16]/90 px-4 py-2 text-sm text-[#9fb0c5]">
                  No nodes visible with current filters. Adjust relation filters or focus hops.
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default FabricKnowledgeGraph;
