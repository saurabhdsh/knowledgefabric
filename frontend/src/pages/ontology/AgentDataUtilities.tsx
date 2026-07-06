import * as d3 from 'd3';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiRequest } from '../../utils/api';
import { ontologyApi, OntologyProject, KnowledgeFabricLite } from '../../utils/ontologyApi';
import { renderLlmGraphInsight } from '../../utils/renderLlmGraphInsight';

type FabricDocPayload = {
  documents?: string[];
  metadatas?: Record<string, unknown>[];
  ids?: string[];
};

type GraphNode = { id?: string; label?: string; type?: string; [k: string]: unknown };
type GraphEdge = { source?: string; target?: string; relation?: string; [k: string]: unknown };

type KnowledgeGraphData = {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  node_count?: number;
  edge_count?: number;
  analytics?: Record<string, unknown>;
  llm_insight?: { summary?: string; generated?: boolean };
  fabric_details?: Record<string, unknown>;
};

type CodeSnippet = { title: string; language: string; code: string };

/** Chevron for native fabric `<select>` so height can match adjacent button. */
const FABRIC_SELECT_BG =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none'%3E%3Cpath stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")";

const CHUNK_PALETTE = ['#22d3ee', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#38bdf8', '#fde047', '#4ade80', '#e879f9', '#2dd4bf'];

function hashLabel(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i += 1) h = Math.imul(31, h) + s.charCodeAt(i) || 0;
  return Math.abs(h);
}

/** Packed bubble scatter — circle area ∝ chunk count; hue per type for quick scanning. */
function ChunkTypeScatterPack({
  counts,
  loading,
}: {
  counts: Record<string, number>;
  loading?: boolean;
}) {
  const [hover, setHover] = useState<null | { name: string; value: number; pct: string }>(null);

  const model = useMemo(() => {
    const entries = Object.entries(counts)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1]);
    const total = d3.sum(entries, (d) => d[1]) || 1;
    if (entries.length === 0) return null;

    const width = 640;
    const height = 320;
    type NodeData = { name: string; value?: number; children?: { name: string; value: number }[] };
    const root = d3
      .hierarchy<NodeData>({
        name: 'root',
        children: entries.map(([name, value]) => ({ name, value })),
      })
      .sum((d) => d.value ?? 0);

    const leaves = d3.pack<NodeData>().size([width, height]).padding(5)(root).leaves();

    const nodes = leaves.map((leaf, i) => {
      const data = leaf.data as { name: string; value: number };
      const name = data.name;
      const value = typeof leaf.value === 'number' ? leaf.value : Number(data.value ?? 0);
      return {
        glowId: i,
        x: leaf.x,
        y: leaf.y,
        r: leaf.r,
        name,
        value,
        pct: ((value / total) * 100).toFixed(1),
        color: CHUNK_PALETTE[hashLabel(name) % CHUNK_PALETTE.length],
      };
    });

    return { nodes, width, height, total, entries };
  }, [counts]);

  if (loading) {
    return (
      <div className="relative h-[320px] animate-pulse overflow-hidden rounded-2xl border border-cyan-500/15 bg-[linear-gradient(120deg,rgba(15,23,42,0.9),rgba(30,41,59,0.5),rgba(15,23,42,0.9))] bg-[length:200%_100%]" />
    );
  }

  if (!model) {
    return (
      <div className="flex h-[200px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/20 text-sm text-[#64748b]">
        No chunk_type metadata on indexed documents yet.
      </div>
    );
  }

  const { nodes, width, height, total, entries } = model;

  return (
    <div className="relative">
      {hover && (
        <div
          className="pointer-events-none absolute left-3 top-3 z-20 rounded-xl border border-white/15 bg-[#0f172a]/95 px-3 py-2 text-xs shadow-xl backdrop-blur-md"
          role="status"
        >
          <p className="font-mono text-[11px] font-semibold text-[#5ec8f2]">{hover.name}</p>
          <p className="mt-1 tabular-nums text-[#e2e8f0]">
            <span className="text-lg font-semibold text-white">{hover.value}</span>
            <span className="text-[#94a3b8]"> chunks</span>
            <span className="ml-2 text-[#a78bfa]">({hover.pct}%)</span>
          </p>
        </div>
      )}

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full max-h-[320px] overflow-visible"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {nodes.map((n) => (
            <radialGradient key={`${n.name}-${n.glowId}`} id={`chunk-glow-${n.glowId}`} cx="35%" cy="30%" r="65%">
              <stop offset="0%" stopColor={n.color} stopOpacity={0.95} />
              <stop offset="55%" stopColor={n.color} stopOpacity={0.45} />
              <stop offset="100%" stopColor="#0f172a" stopOpacity={0.85} />
            </radialGradient>
          ))}
          <filter id="chunk-soft-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="2.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect width={width} height={height} fill="transparent" />

        {nodes.map((n) => (
          <g
            key={n.name}
            transform={`translate(${n.x},${n.y})`}
            onMouseEnter={() => setHover({ name: n.name, value: n.value, pct: n.pct })}
            onMouseLeave={() => setHover(null)}
            className="cursor-crosshair"
          >
            <circle
              r={n.r}
              fill={`url(#chunk-glow-${n.glowId})`}
              stroke="rgba(255,255,255,0.12)"
              strokeWidth={1.5}
              filter="url(#chunk-soft-glow)"
            />
            {n.r >= 26 && (
              <>
                <text
                  textAnchor="middle"
                  dy="-0.15em"
                  fill="#f8fafc"
                  className="pointer-events-none"
                  style={{ fontSize: Math.min(13, n.r / 2.8), fontWeight: 600 }}
                >
                  {n.name.length > 14 ? `${n.name.slice(0, 12)}…` : n.name}
                </text>
                <text
                  textAnchor="middle"
                  dy="1.15em"
                  fill="#cbd5e1"
                  className="pointer-events-none font-mono"
                  style={{ fontSize: Math.min(12, n.r / 3.2) }}
                >
                  {n.value}
                </text>
              </>
            )}
            {n.r < 26 && n.r >= 14 && (
              <text
                textAnchor="middle"
                dy="0.35em"
                fill="#ffffff"
                className="pointer-events-none font-mono"
                style={{ fontSize: n.r / 2.2, fontWeight: 600 }}
              >
                {n.value}
              </text>
            )}
          </g>
        ))}
      </svg>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {entries.map(([name, value]) => {
          const pct = ((value / total) * 100).toFixed(1);
          const color = CHUNK_PALETTE[hashLabel(name) % CHUNK_PALETTE.length];
          return (
            <div
              key={name}
              className="flex items-center justify-between gap-2 rounded-xl border border-white/[0.06] bg-black/25 px-3 py-2 text-[11px]"
              onMouseEnter={() => setHover({ name, value, pct })}
              onMouseLeave={() => setHover(null)}
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full shadow-[0_0_10px_currentColor]" style={{ backgroundColor: color, color }} />
                <span className="truncate font-mono text-[#94a3b8]" title={name}>{name}</span>
              </span>
              <span className="shrink-0 tabular-nums">
                <span className="font-semibold text-[#e2e8f0]">{value}</span>
                <span className="ml-2 text-[#64748b]">{pct}%</span>
              </span>
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-[#64748b]">
        Bubble area scales with chunk count; compare shapes to see which types dominate retrieval. Hover any bubble or row for exact counts and share of total ({total} chunks).
      </p>
    </div>
  );
}

function buildCodingAssistantSnippets(
  fabricId: string,
  query: string,
  apiBase: string
): CodeSnippet[] {
  const escapedQuery = query.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  return [
    {
      title: 'Python · Query fabric (same as Talk to Data)',
      language: 'python',
      code: `import requests

FABRIC_ID = "${fabricId}"
API = "${apiBase}"

resp = requests.post(
    f"{API}/api/v1/knowledge/query/{FABRIC_ID}",
    json={"query": """${escapedQuery || 'Your prompt here'}""", "llm_provider": "openai"},
    timeout=60,
)
resp.raise_for_status()
data = resp.json()
print(data.get("data", {}).get("answer", ""))`,
    },
    {
      title: 'curl · Smoke test',
      language: 'bash',
      code: `curl -s -X POST "${apiBase}/api/v1/knowledge/query/${fabricId}" \\
  -H "Content-Type: application/json" \\
  -d '{"query":"${escapedQuery || 'Return duplicate counts by label'}","llm_provider":"openai"}' | jq .`,
    },
    {
      title: 'Prompt pattern · Structured agent output',
      language: 'text',
      code: `Return JSON only with keys: decision, confidence_0_1, evidence_fields[], reasoning_one_line.
Ground every field in fabric chunks. If uncertain, set decision to "human_review".`,
    },
  ];
}

function deriveRecommendations(params: {
  query: string;
  answer: string;
  confidence: number;
  chunkCount: number;
  nodeCount: number;
  edgeCount: number;
  chunkTypeCounts: Record<string, number>;
}): { recommendations: string[]; tips: string[] } {
  const { query, answer, confidence, chunkCount, nodeCount, edgeCount, chunkTypeCounts } = params;
  const recommendations: string[] = [];
  const tips: string[] = [];

  if (!query.trim()) {
    recommendations.push('Add a concrete prompt before running — vague asks produce vague retrieval.');
    tips.push('Prefix with role + task + output shape, e.g. “You are a claims duplicate analyst. Return JSON…”');
  }
  if (answer.length < 80) {
    recommendations.push('Answer is short — increase specificity or ask for structured JSON with required keys.');
    tips.push('Include anchor IDs (claim_id, prior_matching_claim_id) when your fabric uses relational chunks.');
  }
  if (confidence > 0 && confidence < 0.72) {
    recommendations.push(`Confidence ${confidence.toFixed(2)} suggests retrieval mismatch or under-specified prompt.`);
    tips.push('Split into two steps: (1) retrieve by ID (2) summarize — mirrors deterministic + LLM hybrid.');
  }
  if (chunkCount === 0) {
    recommendations.push('No vector chunks loaded for this fabric — rebuild or re-upload the source.');
  } else if (chunkCount < 50) {
    recommendations.push(`Only ${chunkCount} chunks indexed — edge-case coverage may be thin for agents.`);
  }
  if (nodeCount < 5 && edgeCount < 5) {
    recommendations.push('Graph is sparse — pair/group chunking or richer source may improve relational answers.');
  }
  const linkedPairs = chunkTypeCounts['linked_pair'] ?? chunkTypeCounts['duplicate_pair'] ?? 0;
  if (linkedPairs > 0) {
    tips.push(`Detected ~${linkedPairs} linked-pair chunks — prompts should reference both sides of a relationship when reasoning.`);
  }
  if (recommendations.length === 0) {
    recommendations.push('Fabric response looks usable — save this prompt as a regression test for your agent.');
  }
  if (tips.length === 0) {
    tips.push('Version prompts in git and log fabric_id + prompt hash for reproducible agent evals.');
  }

  return { recommendations, tips };
}

/** Evergreen agent-design guidance for high-volume / multi-query workloads (merged in UI with run-specific tips). */
function collectEvergreenAgentTips(ctx: {
  chunkCount: number;
  nodeCount: number;
  edgeCount: number;
  chunkTypeCounts: Record<string, number>;
  chunkTypeVariety: number;
}): string[] {
  const tips: string[] = [];
  const add = (s: string) => {
    if (!tips.includes(s)) tips.push(s);
  };

  add('For many queries: cache answers by (fabric_id, normalized_prompt, source_version) and invalidate when the fabric is re-ingested.');
  add('Stagger parallel agent calls to the same fabric to avoid vector/LLM spikes; use a small queue or backoff on 429/503.');
  add('Maintain a prompt regression pack (10–30 prompts) that you run after every fabric rebuild — same fabric id, new chunk layout.');
  add('Keep retrieval scope explicit in multi-turn chats (e.g. claim_id, date range) so each query does not “drift” across unrelated chunks.');
  add('Log chunk_ids or metadata keys returned per query in dev; when answers go wrong, compare retrieved chunks to your intent.');
  add('If agents issue similar questions repeatedly, add a thin routing layer: ID lookups vs semantic search vs aggregate prompts — each stresses the fabric differently.');
  add('Expand coverage by varying phrasing in tests — synonyms and edge IDs catch retrieval gaps that one template prompt will miss.');
  add('Cap concurrent “wide” questions (full-corpus summaries); serialize them or precompute rollups at ingest if latency matters.');
  if (ctx.chunkCount > 200) {
    add('Large chunk counts: prefer narrow prompts and required fields in the answer schema so retrieval does not pull noisy neighbors.');
  }
  if (ctx.chunkTypeVariety > 4) {
    add('Several chunk types in this fabric — document which agent flows use which types (row vs pair vs summary) to avoid mixing semantics.');
  }
  if (ctx.nodeCount < 8 && ctx.edgeCount < 8) {
    add('Sparse graph: questions that need named-entity linking across documents may need richer ingestion or a supplemental ontology, not just more prompts.');
  }
  return tips;
}

type FabricFitVerdict = 'strong_fit' | 'likely_ok' | 'uncertain' | 'poor_fit' | 'needs_rebuild';

type PromptFabricFitResult = {
  verdict: FabricFitVerdict;
  headline: string;
  summary: string;
  matchedSignals: string[];
  watchouts: string[];
  fabricActions: string[];
};

/** Offline heuristic: whether this fabric’s shape matches the user’s intended prompt (no extra API call). */
function assessPromptFabricFit(params: {
  prompt: string;
  chunkCount: number;
  nodeCount: number;
  edgeCount: number;
  chunkTypeCounts: Record<string, number>;
  sourceType?: string;
}): PromptFabricFitResult {
  const p = params.prompt.trim().toLowerCase();
  const matchedSignals: string[] = [];
  const watchouts: string[] = [];
  const fabricActions: string[] = [];

  const linkedPairs =
    (params.chunkTypeCounts.linked_pair ?? 0) + (params.chunkTypeCounts.duplicate_pair ?? 0);
  const rowLike =
    (params.chunkTypeCounts.row ?? 0) +
    (params.chunkTypeCounts.csv_row ?? 0) +
    (params.chunkTypeCounts.record ?? 0);

  if (!p.length) {
    return {
      verdict: 'uncertain',
      headline: 'Add a prompt to analyze',
      summary: 'Paste the agent prompt or user question you plan to run repeatedly.',
      matchedSignals,
      watchouts: ['Empty input cannot be matched against chunk types or coverage.'],
      fabricActions: ['Write the concrete task + output shape you expect from the agent.'],
    };
  }

  if (params.chunkCount === 0) {
    return {
      verdict: 'needs_rebuild',
      headline: 'Fabric has no indexed chunks',
      summary: 'Nothing is retrievable until documents are ingested into this fabric.',
      matchedSignals: ['chunk_count = 0'],
      watchouts: ['Any prompt will hallucinate or fail unless vectors exist.'],
      fabricActions: [
        'Re-upload or re-run ingestion for this fabric.',
        'Confirm the backend finished embedding and that GET …/documents returns rows.',
      ],
    };
  }

  const wantsDup =
    /\b(duplicate|dedup|near[-\s]?duplicate|pair|prior\s+match|same\s+claim|match\s+type)\b/i.test(p);
  const wantsAgg =
    /\b(count|how\s+many|aggregate|sum|total|breakdown|distribution|statistics|group\s+by)\b/i.test(p);
  const wantsId =
    /\b(claim_id|clm\d+|policy_id|patient\s*id|member\s*id|invoice|ticket)\b/i.test(p);
  const wantsCrossDoc =
    /\b(relationship|link|graph|entity|across\s+documents|compare\s+two)\b/i.test(p);
  const wantsRealtime =
    /\b(live|real[\s-]?time|today'?s|current\s+stock|api\s+outside|internet|browse)\b/i.test(p);

  if (wantsDup) {
    matchedSignals.push('Prompt targets duplicate / pair reasoning');
    if (linkedPairs === 0) {
      watchouts.push('No linked_pair / duplicate_pair chunks detected — duplicate reasoning may be weak or wrong.');
      fabricActions.push(
        'Recreate or augment ingestion so pair-wise or relational chunks are built (not only isolated rows).'
      );
    } else {
      matchedSignals.push(`~${linkedPairs} pair-oriented chunks present`);
    }
  }

  if (wantsAgg) {
    matchedSignals.push('Prompt asks for counts or aggregates');
    if (params.chunkCount < 30 && rowLike < 5) {
      watchouts.push('Small corpus or few row-like chunks — aggregate answers may be incomplete.');
      fabricActions.push('Consider adding full-table row chunks or a summary statistics layer at ingest time.');
    }
  }

  if (wantsId) {
    matchedSignals.push('Prompt references explicit IDs');
    if (rowLike === 0 && linkedPairs === 0) {
      watchouts.push('Chunk types do not obviously include row/record chunks — ID grounding may miss.');
    }
  }

  if (wantsCrossDoc) {
    matchedSignals.push('Prompt implies cross-record / graph-style reasoning');
    if (params.nodeCount < 6 || params.edgeCount < 6) {
      watchouts.push('Knowledge graph is sparse — relational answers may rely too heavily on the LLM.');
      fabricActions.push('Enrich source data or chunking so co-occurrence / pairs populate the graph.');
    }
  }

  if (wantsRealtime) {
    watchouts.push('Fabric is static knowledge — it cannot replace live APIs or the open web for “current” facts.');
    fabricActions.push('Keep real-time data in tools/APIs; use the fabric for policy, history, and grounded text.');
  }

  if (p.length < 24) {
    watchouts.push('Very short prompt — retrieval may be ambiguous under load; agents should send role + task + format.');
  }

  let verdict: FabricFitVerdict = 'likely_ok';
  if (wantsDup && linkedPairs === 0 && params.chunkCount > 0) {
    verdict = 'poor_fit';
  } else if (watchouts.length >= 3) {
    verdict = 'poor_fit';
  } else if (matchedSignals.length >= 2 && watchouts.length === 0) {
    verdict = 'strong_fit';
  } else if (watchouts.length >= 1 && (params.chunkCount < 40 || wantsDup)) {
    verdict = 'uncertain';
  } else if (watchouts.length === 0 && matchedSignals.length >= 1) {
    verdict = 'likely_ok';
  }

  if (verdict !== 'poor_fit' && params.chunkCount < 25) {
    if (verdict === 'strong_fit') verdict = 'likely_ok';
    else if (verdict === 'likely_ok') verdict = 'uncertain';
    watchouts.push(`Only ${params.chunkCount} chunks — stress-test with edge prompts before production traffic.`);
  }

  const headline: Record<FabricFitVerdict, string> = {
    strong_fit: 'Strong fit for this prompt shape',
    likely_ok: 'Likely usable — validate with a live run',
    uncertain: 'Uncertain fit — tighten prompt or enrich fabric',
    poor_fit: 'Poor fit — fabric shape mismatches the prompt',
    needs_rebuild: 'Rebuild required',
  };

  const summary =
    verdict === 'strong_fit'
      ? 'Chunk types and coverage align with what this prompt is asking for. Still run Talk to Data once to confirm behavior.'
      : verdict === 'likely_ok'
        ? 'No major red flags from chunk layout alone; watch confidence and retrieval in production.'
        : verdict === 'uncertain'
          ? 'Mixed signals — reduce ambiguity in the prompt or add the missing chunk types / sources.'
          : verdict === 'poor_fit'
            ? 'The fabric probably does not support this query class well without ingestion or schema changes.'
            : 'Fix ingestion before investing in agent logic.';

  if (fabricActions.length === 0) {
    fabricActions.push(
      'If answers drift after source updates, bump a fabric version and re-run your regression prompts.'
    );
  }

  return {
    verdict,
    headline: headline[verdict],
    summary,
    matchedSignals,
    watchouts,
    fabricActions,
  };
}

const FIT_VERDICT_STYLES: Record<FabricFitVerdict, string> = {
  strong_fit: 'border-emerald-400/35 bg-emerald-500/10 text-emerald-100',
  likely_ok: 'border-cyan-400/35 bg-cyan-500/10 text-cyan-100',
  uncertain: 'border-amber-400/35 bg-amber-500/10 text-amber-100',
  poor_fit: 'border-orange-400/35 bg-orange-500/10 text-orange-100',
  needs_rebuild: 'border-rose-400/40 bg-rose-500/12 text-rose-100',
};

function ConnectingFabricOverlay({
  fabricLabel,
  fabricId,
}: {
  fabricLabel: string;
  fabricId: string;
}) {
  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-[#020617]/80 px-4 py-8 backdrop-blur-md motion-reduce:backdrop-blur-sm"
      role="alertdialog"
      aria-busy="true"
      aria-live="polite"
      aria-label="Connecting to knowledge fabric"
    >
      <div className="relative w-full max-w-md overflow-hidden rounded-3xl border border-[rgba(94,200,242,0.28)] bg-[linear-gradient(165deg,rgba(12,18,32,0.97),rgba(4,8,16,0.99))] p-10 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_32px_120px_-20px_rgba(34,211,238,0.15)]">
        <div className="pointer-events-none absolute -left-1/2 -top-1/2 h-[200%] w-[200%] motion-reduce:hidden">
          <div className="absolute left-1/2 top-1/2 h-full w-full -translate-x-1/2 -translate-y-1/2 animate-fabric-orbit bg-[conic-gradient(from_90deg_at_50%_50%,transparent_0%,rgba(34,211,238,0.12)_18%,transparent_35%,rgba(167,139,250,0.14)_52%,transparent_70%,rgba(244,114,182,0.1)_85%,transparent_100%)] blur-3xl" />
        </div>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-10%,rgba(94,200,242,0.12),transparent)]" />

        <div className="relative text-center">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.4em] text-[#5ec8f2]/90">Live handshake</p>
          <h2 className="animate-fabric-shimmer mt-5 bg-gradient-to-r from-[#a5f3fc] via-white to-[#ddd6fe] bg-clip-text text-2xl font-semibold tracking-tight text-transparent motion-reduce:animate-none md:text-3xl">
            Connecting to Fabric
          </h2>
          <p className="mt-2 truncate text-sm font-medium text-[#e2e8f0]" title={fabricLabel}>
            {fabricLabel}
          </p>
          <p className="mt-1 font-mono text-[10px] text-[#64748b]">{fabricId}</p>

          <div className="mx-auto mt-8 flex h-12 max-w-[240px] items-end justify-center gap-[7px] motion-reduce:opacity-90">
            {[0, 1, 2, 3, 4, 5, 6].map((i) => (
              <span
                key={i}
                className="inline-block h-10 w-2 origin-bottom rounded-full bg-gradient-to-t from-cyan-600 via-cyan-400 to-violet-400 shadow-[0_0_12px_rgba(34,211,238,0.35)] motion-reduce:animate-none animate-fabric-pulse-bar"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
          <p className="mt-6 text-[11px] leading-relaxed text-[#64748b]">
            Syncing vector chunks and knowledge graph…
          </p>
        </div>
      </div>
    </div>
  );
}

const AgentDataUtilities: React.FC = () => {
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const [projects, setProjects] = useState<OntologyProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [versions, setVersions] = useState<Array<{ id: string; version_label: string; is_draft: boolean }>>([]);
  const [selectedVersionId, setSelectedVersionId] = useState('');
  const [fabrics, setFabrics] = useState<KnowledgeFabricLite[]>([]);
  const [selectedFabricId, setSelectedFabricId] = useState('');

  const [fabricDocs, setFabricDocs] = useState<FabricDocPayload | null>(null);
  const [docsLoading, setDocsLoading] = useState(false);
  const [graphPayload, setGraphPayload] = useState<KnowledgeGraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphRefreshedAt, setGraphRefreshedAt] = useState('');

  const [talkQuery, setTalkQuery] = useState('');
  const [talkLoading, setTalkLoading] = useState(false);
  const [talkResult, setTalkResult] = useState<Record<string, unknown> | null>(null);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [tips, setTips] = useState<string[]>([]);

  const [ontologyOpen, setOntologyOpen] = useState(false);
  const [ontologyQuery, setOntologyQuery] = useState('');
  const [topK, setTopK] = useState(12);
  const [ontologyResult, setOntologyResult] = useState<Record<string, unknown> | null>(null);
  const [ontologyLoading, setOntologyLoading] = useState(false);

  const [chunkPanelLimit, setChunkPanelLimit] = useState(40);

  const [fabricFitPrompt, setFabricFitPrompt] = useState('');
  const [fabricFitResult, setFabricFitResult] = useState<PromptFabricFitResult | null>(null);

  useEffect(() => {
    ontologyApi.listProjects().then((data) => {
      setProjects(data);
      if (data.length > 0) setSelectedProjectId(data[0].id);
    }).catch(() => setProjects([]));
    ontologyApi.listKnowledgeFabrics().then((data) => {
      setFabrics(data);
      if (data.length > 0) setSelectedFabricId(data[0].id);
    }).catch(() => setFabrics([]));
  }, []);

  const refreshFabricData = useCallback(async (fabricId: string) => {
    if (!fabricId) {
      setFabricDocs(null);
      setGraphPayload(null);
      return;
    }
    setDocsLoading(true);
    setGraphLoading(true);
    try {
      const [docsRes, graphRes] = await Promise.all([
        apiRequest(`api/v1/knowledge/${fabricId}/documents`),
        apiRequest(`api/v1/knowledge/${fabricId}/knowledge-graph?include_llm=true`),
      ]);
      const docsJson = await docsRes.json();
      setFabricDocs(docsJson as FabricDocPayload);

      const graphJson = await graphRes.json();
      if (graphJson?.success && graphJson?.data) {
        setGraphPayload(graphJson.data as KnowledgeGraphData);
      } else {
        setGraphPayload(null);
      }
      setGraphRefreshedAt(new Date().toLocaleTimeString());
    } catch {
      setFabricDocs(null);
      setGraphPayload(null);
    } finally {
      setDocsLoading(false);
      setGraphLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshFabricData(selectedFabricId);
  }, [selectedFabricId, refreshFabricData]);

  useEffect(() => {
    if (!selectedProjectId) {
      setVersions([]);
      return;
    }
    ontologyApi.listVersions(selectedProjectId).then((data) => {
      setVersions(data);
      if (data.length > 0) setSelectedVersionId(data[0].id);
    }).catch(() => setVersions([]));
  }, [selectedProjectId]);

  const activeFabric = useMemo(
    () => fabrics.find((f) => f.id === selectedFabricId),
    [fabrics, selectedFabricId]
  );

  const fabricDetails = graphPayload?.fabric_details ?? {};

  const { documents, metadatas, docIds } = useMemo(
    () => ({
      documents: fabricDocs?.documents ?? [],
      metadatas: fabricDocs?.metadatas ?? [],
      docIds: fabricDocs?.ids ?? [],
    }),
    [fabricDocs]
  );

  const chunkTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const m of metadatas) {
      const ct = String((m?.chunk_type as string) || 'unknown');
      counts[ct] = (counts[ct] || 0) + 1;
    }
    return counts;
  }, [metadatas]);

  const nodes = graphPayload?.nodes ?? [];
  const edges = graphPayload?.edges ?? [];

  const evergreenAgentTips = useMemo(
    () =>
      collectEvergreenAgentTips({
        chunkCount: documents.length,
        nodeCount: Number(graphPayload?.node_count ?? nodes.length ?? 0),
        edgeCount: Number(graphPayload?.edge_count ?? edges.length ?? 0),
        chunkTypeCounts,
        chunkTypeVariety: Object.keys(chunkTypeCounts).length,
      }),
    [documents.length, graphPayload?.node_count, graphPayload?.edge_count, nodes.length, edges.length, chunkTypeCounts]
  );

  const mergedDesignTips = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const t of evergreenAgentTips) {
      if (!seen.has(t)) {
        seen.add(t);
        out.push(t);
      }
    }
    for (const t of tips) {
      if (!seen.has(t)) {
        seen.add(t);
        out.push(t);
      }
    }
    return out;
  }, [evergreenAgentTips, tips]);
  const analytics = (graphPayload?.analytics ?? {}) as Record<string, unknown>;

  const talkAnswer = String((talkResult?.data as Record<string, unknown> | undefined)?.answer ?? '');
  const talkConfidence = Number((talkResult?.data as Record<string, unknown> | undefined)?.confidence ?? 0);
  const talkProvider = String((talkResult?.data as Record<string, unknown> | undefined)?.llm_provider ?? '');

  const runTalkToData = async () => {
    if (!talkQuery.trim() || !selectedFabricId) return;
    setTalkLoading(true);
    setTalkResult(null);
    try {
      const response = await apiRequest(`api/v1/knowledge/query/${selectedFabricId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: talkQuery.trim(), llm_provider: 'openai' }),
      });
      const data = await response.json();
      setTalkResult(data);

      const nodeCount = Number(graphPayload?.node_count ?? nodes.length ?? 0);
      const edgeCount = Number(graphPayload?.edge_count ?? edges.length ?? 0);
      const rec = deriveRecommendations({
        query: talkQuery,
        answer: String((data?.data as Record<string, unknown> | undefined)?.answer ?? ''),
        confidence: Number((data?.data as Record<string, unknown> | undefined)?.confidence ?? 0),
        chunkCount: documents.length,
        nodeCount,
        edgeCount,
        chunkTypeCounts,
      });
      setRecommendations(rec.recommendations);
      setTips(rec.tips);
    } catch (e) {
      setTalkResult({ success: false, error: e instanceof Error ? e.message : 'Request failed' });
      setRecommendations(['Request failed — check backend and fabric id.']);
      setTips(['Verify REACT_APP_API_URL and that the fabric exists on the server.']);
    } finally {
      setTalkLoading(false);
    }
  };

  const codingSnippets = useMemo(
    () => buildCodingAssistantSnippets(selectedFabricId, talkQuery, apiBase),
    [selectedFabricId, talkQuery, apiBase]
  );

  const runOntologyQuery = async () => {
    if (!ontologyQuery.trim() || !selectedProjectId || !selectedVersionId) return;
    setOntologyLoading(true);
    try {
      const data = await ontologyApi.agentQuery({
        project_id: selectedProjectId,
        version_id: selectedVersionId,
        query: ontologyQuery.trim(),
        top_k: topK,
        role: 'agent_developer',
        include_debug: true,
      });
      setOntologyResult(data);
    } finally {
      setOntologyLoading(false);
    }
  };

  const displayedChunks = useMemo(() => {
    const limit = Math.min(chunkPanelLimit, documents.length);
    const out: Array<{ idx: number; text: string; meta: Record<string, unknown>; id: string }> = [];
    for (let i = 0; i < limit; i++) {
      const text = documents[i] ?? '';
      const meta = (metadatas[i] ?? {}) as Record<string, unknown>;
      const id = String(docIds[i] ?? `idx-${i}`);
      out.push({ idx: i + 1, text, meta, id });
    }
    return out;
  }, [documents, metadatas, docIds, chunkPanelLimit]);

  useEffect(() => {
    setFabricFitResult(null);
  }, [selectedFabricId]);

  const runFabricFitCheck = useCallback(() => {
    const fd = (graphPayload?.fabric_details ?? {}) as { source_type?: string };
    setFabricFitResult(
      assessPromptFabricFit({
        prompt: fabricFitPrompt,
        chunkCount: documents.length,
        nodeCount: Number(graphPayload?.node_count ?? nodes.length ?? 0),
        edgeCount: Number(graphPayload?.edge_count ?? edges.length ?? 0),
        chunkTypeCounts,
        sourceType: String(fd.source_type ?? activeFabric?.source_type ?? ''),
      })
    );
  }, [fabricFitPrompt, documents.length, graphPayload, chunkTypeCounts, activeFabric?.source_type, nodes.length, edges.length]);

  const fabricFetching = Boolean(selectedFabricId && (docsLoading || graphLoading));

  return (
    <div className="relative min-h-[calc(100vh-6rem)] text-[#cbd5e1]">
      {fabricFetching && (
        <ConnectingFabricOverlay fabricLabel={activeFabric?.name ?? selectedFabricId} fabricId={selectedFabricId} />
      )}
      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl border border-[rgba(94,200,242,0.22)] bg-[radial-gradient(ellipse_120%_80%_at_50%_-20%,rgba(94,200,242,0.18),transparent),radial-gradient(ellipse_80%_50%_at_100%_50%,rgba(139,92,246,0.12),transparent),#070b12] px-6 py-10 md:px-10 md:py-12">
        <div className="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%2394a3b8\' fill-opacity=\'0.06\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')] opacity-80" />
        <div className="relative max-w-5xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#5ec8f2]/90">Agent developer studio</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#f1f5f9] md:text-4xl">
            Fabric intelligence &amp; <span className="bg-gradient-to-r from-[#5ec8f2] via-[#a78bfa] to-[#f472b6] bg-clip-text text-transparent">Talk to Data</span>
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#94a3b8]">
            Inspect every chunk, graph node, and signal for the fabric your agents will call — then validate prompts with actionable recommendations and copy-paste integration code.
          </p>

          <div className="mt-8 max-w-2xl space-y-2">
            <span className="block text-xs font-medium uppercase tracking-[0.14em] text-[#64748b]">Knowledge fabric</span>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
              <select
                value={selectedFabricId}
                onChange={(e) => setSelectedFabricId(e.target.value)}
                style={{ backgroundImage: FABRIC_SELECT_BG }}
                className="h-12 min-h-[48px] w-full flex-1 appearance-none rounded-2xl border border-[rgba(148,163,184,0.25)] bg-[#0c1220]/90 bg-[length:1rem] bg-[position:right_0.75rem_center] bg-no-repeat px-4 pr-10 text-sm font-medium leading-normal text-[#e2e8f0] shadow-inner shadow-black/20 backdrop-blur-sm transition focus:border-[rgba(94,200,242,0.45)] focus:outline-none focus:ring-2 focus:ring-[rgba(94,200,242,0.25)]"
              >
                <option value="">Select a fabric</option>
                {fabrics.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => refreshFabricData(selectedFabricId)}
                disabled={!selectedFabricId || docsLoading || graphLoading}
                className="inline-flex h-12 min-h-[48px] shrink-0 items-center justify-center whitespace-nowrap rounded-2xl border border-[rgba(148,163,184,0.25)] bg-[#0c1220]/90 px-6 text-sm font-semibold text-[#e2e8f0] shadow-inner shadow-black/20 backdrop-blur-sm transition hover:border-[rgba(94,200,242,0.4)] hover:bg-[#0f172a]/95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Refresh data
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Fabric snapshot */}
      {selectedFabricId && (
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            { label: 'Indexed chunks', value: documents.length, hint: 'Vector store documents', accent: 'from-cyan-500/20 to-blue-500/10 border-cyan-500/25' },
            { label: 'Graph nodes', value: Number(graphPayload?.node_count ?? nodes.length ?? 0), hint: 'Entity-like tokens', accent: 'from-violet-500/20 to-fuchsia-500/10 border-violet-500/25' },
            { label: 'Graph edges', value: Number(graphPayload?.edge_count ?? edges.length ?? 0), hint: 'Co-occurrence links', accent: 'from-amber-500/20 to-orange-500/10 border-amber-500/25' },
            { label: 'Fabric chunks (meta)', value: Number(fabricDetails.total_chunks ?? 0) || documents.length, hint: 'Reported total_chunks', accent: 'from-emerald-500/20 to-teal-500/10 border-emerald-500/25' },
          ].map((card) => (
            <div
              key={card.label}
              className={`rounded-2xl border bg-gradient-to-br ${card.accent} p-4 backdrop-blur-sm`}
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#94a3b8]">{card.label}</p>
              <p className="mt-2 font-mono text-3xl font-semibold tabular-nums text-[#f8fafc]">{card.value}</p>
              <p className="mt-1 text-[11px] text-[#64748b]">{card.hint}</p>
            </div>
          ))}
        </div>
      )}

      {/* Talk to Data — primary */}
      {selectedFabricId && (
        <section className="mt-10 rounded-3xl border border-[rgba(167,139,250,0.2)] bg-[linear-gradient(145deg,rgba(15,23,42,0.95),rgba(8,11,18,0.98))] p-6 shadow-[0_24px_80px_-24px_rgba(0,0,0,0.65)] md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/[0.06] pb-6">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#a78bfa]">01 · Talk to Data</p>
              <h2 className="mt-2 text-xl font-semibold text-[#f8fafc]">Validate prompts against live fabric context</h2>
              <p className="mt-2 max-w-2xl text-sm text-[#94a3b8]">
                Same API your agents use. You get the answer, confidence, tailored recommendations, and integration snippets for this fabric.
              </p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {[
              'Return duplicate counts by duplicate_match_type as JSON.',
              'For claim CLM101820: prior match, match type, route, and key field deltas.',
              'List 3 near-duplicate pairs with claim_id and risk score.',
            ].map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => setTalkQuery(chip)}
                className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-left text-[11px] text-[#cbd5e1] transition hover:border-[rgba(94,200,242,0.35)] hover:bg-[rgba(94,200,242,0.08)]"
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_380px]">
            <div className="space-y-4">
              <textarea
                value={talkQuery}
                onChange={(e) => setTalkQuery(e.target.value)}
                placeholder="Ask anything you want your external agent to resolve — be specific about IDs and output format."
                className="min-h-[140px] w-full resize-y rounded-2xl border border-[rgba(51,65,85,0.5)] bg-[#020617]/80 px-4 py-3 font-mono text-sm leading-relaxed text-[#e2e8f0] placeholder:text-[#475569] focus:border-[rgba(94,200,242,0.4)] focus:outline-none focus:ring-1 focus:ring-[rgba(94,200,242,0.2)]"
              />
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={runTalkToData}
                  disabled={talkLoading || !talkQuery.trim()}
                  className="rounded-2xl bg-gradient-to-r from-[#0ea5e9] to-[#6366f1] px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110 disabled:opacity-40"
                >
                  {talkLoading ? 'Running…' : 'Run prompt'}
                </button>
                {talkResult && talkConfidence > 0 && (
                  <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 font-mono text-xs text-[#94a3b8]">
                    confidence <span className="text-[#5ec8f2]">{talkConfidence.toFixed(2)}</span>
                    {talkProvider && <span className="ml-2 text-[#64748b]">{talkProvider}</span>}
                  </span>
                )}
              </div>

              {talkResult && (
                <div className="rounded-2xl border border-[rgba(94,200,242,0.2)] bg-[#020617]/50 p-5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#64748b]">Answer</p>
                  <div className="mt-3 whitespace-pre-wrap font-mono text-sm leading-relaxed text-[#e2e8f0]">
                    {talkAnswer || String((talkResult as { error?: string }).error || JSON.stringify(talkResult, null, 2))}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.06] p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-200/90">Recommendations</p>
                <ul className="mt-3 space-y-2 text-xs text-[#fde68a]/95">
                  {(recommendations.length ? recommendations : ['Run a prompt to see recommendations.']).map((r, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-amber-400/80">→</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.06] p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-200/90">Agent design tips</p>
                <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1 text-xs text-[#a7f3d0]/95">
                  {mergedDesignTips.map((t, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="shrink-0 text-emerald-400/80">✓</span>
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Coding assistant */}
          <div className="mt-8 border-t border-white/[0.06] pt-8">
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#64748b]">Coding assistant · This fabric</p>
            <p className="mt-2 text-sm text-[#94a3b8]">
              Drop these into your agent repo — URLs and fabric id are filled for the selection above. Use the prompt fit check to see if this fabric&apos;s chunk layout matches what you plan to ask before you ship agents.
            </p>

            <div className="mt-6 rounded-2xl border border-[rgba(94,200,242,0.22)] bg-[linear-gradient(135deg,rgba(15,23,42,0.9),rgba(8,11,18,0.95))] p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#5ec8f2]/90">Prompt ↔ fabric fit check</p>
                  <p className="mt-1 text-xs text-[#94a3b8]">
                    Describe the agent prompt or end-user question you care about. We compare it to chunk types, counts, and graph density (offline — no API round trip). Then confirm with <span className="text-[#cbd5e1]">Talk to Data</span> above.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFabricFitPrompt(talkQuery)}
                  disabled={!talkQuery.trim()}
                  className="shrink-0 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-1.5 text-[11px] text-[#cbd5e1] transition hover:bg-white/[0.1] disabled:opacity-30"
                >
                  Copy from Talk to Data
                </button>
              </div>
              <textarea
                value={fabricFitPrompt}
                onChange={(e) => setFabricFitPrompt(e.target.value)}
                placeholder="e.g. List duplicate pairs with claim IDs and explain why they matched…"
                className="mt-4 min-h-[88px] w-full resize-y rounded-xl border border-[rgba(51,65,85,0.55)] bg-[#020617]/85 px-4 py-3 font-mono text-sm text-[#e2e8f0] placeholder:text-[#475569] focus:border-[rgba(94,200,242,0.45)] focus:outline-none focus:ring-1 focus:ring-[rgba(94,200,242,0.2)]"
              />
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={runFabricFitCheck}
                  className="rounded-xl bg-gradient-to-r from-[#0891b2] to-[#6366f1] px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-900/20 transition hover:brightness-110"
                >
                  Analyze prompt vs fabric
                </button>
                <span className="text-[11px] text-[#64748b]">Heuristic only — not a substitute for running the real query.</span>
              </div>

              {fabricFitResult && (
                <div className="mt-6 space-y-4 border-t border-white/[0.06] pt-6">
                  <div className={`rounded-xl border px-4 py-3 ${FIT_VERDICT_STYLES[fabricFitResult.verdict]}`}>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] opacity-90">Verdict</p>
                    <p className="mt-1 text-base font-semibold">{fabricFitResult.headline}</p>
                    <p className="mt-2 text-sm opacity-95">{fabricFitResult.summary}</p>
                  </div>
                  {fabricFitResult.matchedSignals.length > 0 && (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#64748b]">Matched signals</p>
                      <ul className="mt-2 space-y-1 text-xs text-[#cbd5e1]">
                        {fabricFitResult.matchedSignals.map((s) => (
                          <li key={s} className="flex gap-2">
                            <span className="text-[#5ec8f2]">●</span>
                            {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {fabricFitResult.watchouts.length > 0 && (
                    <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-4">
                      <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-amber-200/90">Watch carefully</p>
                      <ul className="mt-2 space-y-1.5 text-xs text-[#fde68a]/95">
                        {fabricFitResult.watchouts.map((w, i) => (
                          <li key={`${i}-${w.slice(0, 48)}`} className="flex gap-2">
                            <span className="shrink-0">⚠</span>
                            {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="rounded-xl border border-violet-500/25 bg-violet-500/[0.06] p-4">
                    <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-violet-200/90">Fabric: tweak prompts vs recreate</p>
                    <ul className="mt-2 space-y-1.5 text-xs text-[#e9d5ff]/95">
                      {fabricFitResult.fabricActions.map((a, i) => (
                        <li key={`${i}-${a.slice(0, 48)}`} className="flex gap-2">
                          <span className="shrink-0 text-violet-400">◇</span>
                          {a}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-1 lg:grid-cols-3">
              {codingSnippets.map((snip) => (
                <div key={snip.title} className="flex flex-col rounded-2xl border border-[rgba(51,65,85,0.6)] bg-[#020617]/90 overflow-hidden">
                  <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2">
                    <span className="text-[11px] font-medium text-[#94a3b8]">{snip.title}</span>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard?.writeText(snip.code)}
                      className="text-[10px] uppercase tracking-wider text-[#5ec8f2] hover:underline"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="max-h-52 overflow-auto p-3 font-mono text-[10px] leading-relaxed text-[#a5b4fc]/95">{snip.code}</pre>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Fabric inspector */}
      {selectedFabricId && (
        <section className="mt-10 space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#64748b]">02 · Fabric inspector</p>
              <h2 className="mt-2 text-xl font-semibold text-[#f8fafc]">Chunks, graph, and metadata for developers</h2>
            </div>
            <p className="text-xs text-[#64748b]">Last graph refresh: {graphRefreshedAt || '—'}</p>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            {/* Identity */}
            <div className="rounded-3xl border border-white/[0.08] bg-[#0a0f18]/90 p-6 lg:col-span-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">Fabric record</p>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-4 border-b border-white/[0.05] pb-2">
                  <dt className="text-[#64748b]">Name</dt>
                  <dd className="text-right font-medium text-[#e2e8f0]">{String(fabricDetails.name ?? activeFabric?.name ?? '—')}</dd>
                </div>
                <div className="flex justify-between gap-4 border-b border-white/[0.05] pb-2">
                  <dt className="text-[#64748b]">Fabric id</dt>
                  <dd className="max-w-[60%] break-all text-right font-mono text-xs text-[#5ec8f2]">{selectedFabricId}</dd>
                </div>
                <div className="flex justify-between gap-4 border-b border-white/[0.05] pb-2">
                  <dt className="text-[#64748b]">Source type</dt>
                  <dd className="text-right text-[#e2e8f0]">{String(fabricDetails.source_type ?? activeFabric?.source_type ?? '—')}</dd>
                </div>
                <div className="flex justify-between gap-4 border-b border-white/[0.05] pb-2">
                  <dt className="text-[#64748b]">Tags</dt>
                  <dd className="text-right text-xs text-[#94a3b8]">
                    {Array.isArray(fabricDetails.tags) ? (fabricDetails.tags as string[]).join(', ') : '—'}
                  </dd>
                </div>
                <div className="pt-1">
                  <dt className="text-[#64748b]">Description</dt>
                  <dd className="mt-2 text-xs leading-relaxed text-[#94a3b8]">{String(fabricDetails.description ?? '—')}</dd>
                </div>
              </dl>
            </div>

            {/* Chunk types — packed scatter + numeric legend */}
            <div className="rounded-3xl border border-white/[0.08] bg-[linear-gradient(165deg,rgba(12,18,32,0.95),rgba(8,11,20,0.98))] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] lg:col-span-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">Chunk type distribution</p>
                  <p className="mt-1 text-sm font-medium text-[#e2e8f0]">Packed bubble map</p>
                </div>
                {Object.keys(chunkTypeCounts).length > 0 && (
                  <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1 font-mono text-[11px] tabular-nums text-cyan-200/95">
                    {Object.keys(chunkTypeCounts).length} types · {documents.length} indexed
                  </span>
                )}
              </div>
              <div className="mt-4">
                <ChunkTypeScatterPack counts={chunkTypeCounts} loading={docsLoading} />
              </div>
              {analytics.top_entities != null && (
                <p className="mt-4 text-[11px] text-[#64748b]">
                  Analytics bundle includes additional signals from the graph builder — use for prompt wording when entities repeat.
                </p>
              )}
            </div>
          </div>

          {/* Chunks table */}
          <div className="rounded-3xl border border-white/[0.08] bg-[#0a0f18]/90 overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
              <div>
                <p className="text-sm font-semibold text-[#f8fafc]">Indexed chunks</p>
                <p className="text-[11px] text-[#64748b]">Showing {Math.min(chunkPanelLimit, documents.length)} of {documents.length}</p>
              </div>
              <button
                type="button"
                onClick={() => setChunkPanelLimit((n) => Math.min(n + 40, documents.length || n + 40))}
                disabled={chunkPanelLimit >= documents.length}
                className="rounded-xl border border-white/10 bg-white/[0.05] px-3 py-1.5 text-xs text-[#cbd5e1] disabled:opacity-30"
              >
                Load more
              </button>
            </div>
            <div className="max-h-[480px] overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-[#070b12] z-10">
                  <tr className="border-b border-white/[0.06] text-[#64748b]">
                    <th className="px-4 py-2 font-medium">#</th>
                    <th className="px-4 py-2 font-medium">chunk_type</th>
                    <th className="px-4 py-2 font-medium">Preview</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedChunks.map((row) => (
                    <tr key={row.id} className="border-b border-white/[0.04] align-top hover:bg-white/[0.02]">
                      <td className="px-4 py-2 font-mono text-[#64748b]">{row.idx}</td>
                      <td className="px-4 py-2 font-mono text-[#a78bfa]">{String(row.meta.chunk_type ?? '—')}</td>
                      <td className="px-4 py-2 max-w-xl">
                        <p className="line-clamp-3 font-mono text-[11px] text-[#cbd5e1]">{row.text}</p>
                        <details className="mt-1">
                          <summary className="cursor-pointer text-[10px] text-[#64748b]">metadata</summary>
                          <pre className="mt-1 max-h-24 overflow-auto rounded bg-black/40 p-2 text-[10px] text-[#94a3b8]">{JSON.stringify(row.meta, null, 2)}</pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                  {!documents.length && !docsLoading && (
                    <tr>
                      <td colSpan={3} className="px-4 py-8 text-center text-[#64748b]">No documents returned for this fabric.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Graph nodes / edges */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-3xl border border-white/[0.08] bg-[#0a0f18]/90 p-5">
              <p className="text-sm font-semibold text-[#f8fafc]">Graph nodes ({nodes.length})</p>
              <div className="mt-3 max-h-64 space-y-2 overflow-auto pr-1">
                {nodes.slice(0, 60).map((n, i) => (
                  <div key={String(n.id ?? i)} className="rounded-xl border border-white/[0.06] bg-black/30 px-3 py-2 text-[11px]">
                    <span className="font-mono text-[#5ec8f2]">{String(n.label ?? n.id ?? 'node')}</span>
                    {n.type != null && <span className="ml-2 text-[#64748b]">{String(n.type)}</span>}
                  </div>
                ))}
                {!nodes.length && !graphLoading && <p className="text-xs text-[#64748b]">No nodes — graph may be minimal for this fabric.</p>}
              </div>
            </div>
            <div className="rounded-3xl border border-white/[0.08] bg-[#0a0f18]/90 p-5">
              <p className="text-sm font-semibold text-[#f8fafc]">Graph edges ({edges.length})</p>
              <div className="mt-3 max-h-64 space-y-2 overflow-auto pr-1">
                {edges.slice(0, 60).map((e, i) => (
                  <div key={i} className="rounded-xl border border-white/[0.06] bg-black/30 px-3 py-2 font-mono text-[11px] text-[#cbd5e1]">
                    <span className="text-[#94a3b8]">{String(e.source ?? '?')}</span>
                    <span className="mx-1 text-fuchsia-400/80">{String(e.relation ?? '—')}</span>
                    <span className="text-[#94a3b8]">{String(e.target ?? '?')}</span>
                  </div>
                ))}
                {!edges.length && !graphLoading && <p className="text-xs text-[#64748b]">No edges yet.</p>}
              </div>
            </div>
          </div>

          {graphPayload?.llm_insight && String((graphPayload.llm_insight as { summary?: string }).summary || '').trim() && (
            <div className="rounded-3xl border border-violet-500/15 bg-[linear-gradient(165deg,rgba(46,16,101,0.12),rgba(15,23,42,0.55))] p-7 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-300/75">LLM graph insight</p>
              <div className="mt-5 text-slate-100 antialiased selection:bg-violet-500/25">
                {renderLlmGraphInsight(String((graphPayload.llm_insight as { summary?: string }).summary))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Advanced ontology — collapsed */}
      <section className="mt-12 rounded-3xl border border-white/[0.06] bg-[#070b12]/80">
        <button
          type="button"
          onClick={() => setOntologyOpen((o) => !o)}
          className="flex w-full items-center justify-between px-6 py-4 text-left"
        >
          <span className="text-sm font-semibold text-[#94a3b8]">Advanced · Ontology query mode</span>
          <span className="text-[#64748b]">{ontologyOpen ? '−' : '+'}</span>
        </button>
        {ontologyOpen && (
          <div className="border-t border-white/[0.06] px-6 py-6 space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} className="rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm">
                <option value="">Project</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <select value={selectedVersionId} onChange={(e) => setSelectedVersionId(e.target.value)} className="rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm">
                <option value="">Version</option>
                {versions.map((v) => <option key={v.id} value={v.id}>{v.version_label}</option>)}
              </select>
            </div>
            <textarea value={ontologyQuery} onChange={(e) => setOntologyQuery(e.target.value)} className="min-h-[80px] w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm" placeholder="Ontology NL query…" />
            <div className="flex items-center gap-4">
              <input type="range" min={3} max={20} value={topK} onChange={(e) => setTopK(Number(e.target.value))} className="accent-[#5ec8f2]" />
              <span className="text-xs text-[#64748b]">top_k {topK}</span>
              <button type="button" onClick={runOntologyQuery} disabled={ontologyLoading || !ontologyQuery.trim()} className="rounded-xl bg-white/[0.08] px-4 py-2 text-sm text-[#e2e8f0] disabled:opacity-40">
                {ontologyLoading ? '…' : 'Run ontology query'}
              </button>
            </div>
            {ontologyResult && (
              <pre className="max-h-64 overflow-auto rounded-xl bg-black/50 p-4 text-[11px] text-[#94a3b8]">{JSON.stringify(ontologyResult, null, 2)}</pre>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

export default AgentDataUtilities;
