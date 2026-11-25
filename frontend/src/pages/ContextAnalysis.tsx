import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowPathIcon,
  CheckIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';
import ContextEvidenceBubble from '../components/ContextEvidenceBubble';

type TabId = 'in-use' | 'queue' | 'overrides' | 'coverage';

interface FabricOption {
  id: string;
  name: string;
  status?: string;
}

interface EnvelopeLine {
  kind: string;
  text: string;
  source_id?: string | null;
  confidence?: number | null;
}

interface Episode {
  id: string;
  query: string;
  answer: string;
  route?: string | null;
  ontology_version_id?: string | null;
  confidence?: number | null;
  created_at?: string | null;
  context_envelope?: {
    route?: string | null;
    ontology_version_id?: string | null;
    confidence?: number | null;
    lines?: EnvelopeLine[];
  } | null;
}

interface Candidate {
  id: string;
  query?: string;
  proposed_fact: string;
  status: string;
  destination?: string;
  classification_reason?: string | null;
  episode_id?: string | null;
}

interface MemoryFact {
  candidate_id?: string;
  fact: string;
  query?: string;
  applied_at?: string;
}

interface CoverageGap {
  query: string;
  count: number;
  gap: 'no_ontology' | 'no_evidence';
  route?: string | null;
  confidence?: number | null;
}

interface Studio {
  fabric_id: string;
  fabric_name: string;
  ontology_project_id?: string | null;
  approved_ontology_version_id?: string | null;
  episodes: Episode[];
  queue: Candidate[];
  overrides: MemoryFact[];
  coverage: CoverageGap[];
  counts: { episodes: number; queued: number; overrides: number; gaps: number };
}

const TABS: { id: TabId; label: string; hint: string }[] = [
  { id: 'in-use', label: 'In use', hint: 'What the last answers were allowed to use' },
  { id: 'queue', label: 'Queue', hint: 'Corrections waiting for a destination' },
  { id: 'overrides', label: 'Overrides', hint: 'Memory that stands in for the source' },
  { id: 'coverage', label: 'Coverage', hint: 'Questions the contract or the evidence could not carry' },
];

const destinationLabel: Record<string, string> = {
  memory: 'Fabric memory',
  ontology_alias: 'Ontology alias',
  ontology_constraint: 'Ontology rule',
  session: 'This session',
  discard: 'Discard',
};

function confidenceLabel(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

const ContextAnalysis: React.FC = () => {
  const [fabrics, setFabrics] = useState<FabricOption[]>([]);
  const [fabricId, setFabricId] = useState('');
  const [studio, setStudio] = useState<Studio | null>(null);
  const [tab, setTab] = useState<TabId>('in-use');
  const [openEpisode, setOpenEpisode] = useState<string | null>(null);
  const [loadingFabrics, setLoadingFabrics] = useState(true);
  const [loadingStudio, setLoadingStudio] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoadingFabrics(true);
      try {
        const response = await apiRequest('api/v1/knowledge/');
        const payload = await response.json();
        const rows = Array.isArray(payload.data) ? payload.data : [];
        setFabrics(rows.map((row: FabricOption) => ({ id: row.id, name: row.name, status: row.status })));
        setFabricId((current) => current || rows[0]?.id || '');
      } catch {
        setBanner({ type: 'error', message: 'Unable to load fabrics. Confirm the API is running.' });
      } finally {
        setLoadingFabrics(false);
      }
    };
    load();
  }, []);

  const loadStudio = useCallback(async (id: string) => {
    if (!id) return;
    setLoadingStudio(true);
    try {
      const response = await apiRequest(`api/v1/agent/fabrics/${encodeURIComponent(id)}/context`);
      const payload = await response.json();
      if (!payload.success) throw new Error(payload.message || 'Context studio failed');
      setStudio(payload.data as Studio);
      setBanner(null);
    } catch (error) {
      setStudio(null);
      setBanner({
        type: 'error',
        message: error instanceof Error ? error.message : 'Unable to load the context layer.',
      });
    } finally {
      setLoadingStudio(false);
    }
  }, []);

  useEffect(() => {
    if (fabricId) loadStudio(fabricId);
  }, [fabricId, loadStudio]);

  const counts = studio?.counts;

  const act = async (path: string, success: string) => {
    setBusyId(path);
    try {
      const response = await apiRequest(path, { method: 'POST' });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Request failed');
      }
      setBanner({ type: 'success', message: success });
      await loadStudio(fabricId);
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Request failed' });
    } finally {
      setBusyId(null);
    }
  };

  const selectedName = useMemo(
    () => fabrics.find((fabric) => fabric.id === fabricId)?.name || studio?.fabric_name || 'Select a fabric',
    [fabrics, fabricId, studio]
  );

  return (
    <div className="ctx-studio mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[#5ec8f2]">Context layer</p>
          <h1 className="mt-1 text-3xl font-semibold text-[#e8edf4]">Context Analysis</h1>
          <p className="mt-2 max-w-2xl text-sm text-[#8b9cb0]">
            The packet each answer used, the corrections waiting to become memory or ontology, and the questions the fabric still cannot carry.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={fabricId}
            onChange={(event) => setFabricId(event.target.value)}
            disabled={loadingFabrics}
            className="min-w-[16rem] rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#10141d]/80 px-3 py-2 text-sm text-[#e8edf4]"
          >
            {fabrics.length === 0 && <option value="">No fabrics</option>}
            {fabrics.map((fabric) => (
              <option key={fabric.id} value={fabric.id}>{fabric.name}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => loadStudio(fabricId)}
            className="rounded-xl border border-[rgba(94,200,242,0.35)] p-2 text-[#5ec8f2] hover:bg-[rgba(94,200,242,0.1)]"
            title="Refresh"
          >
            <ArrowPathIcon className={`h-5 w-5 ${loadingStudio ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {banner && (
        <div
          className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
            banner.type === 'error'
              ? 'border-[rgba(240,137,132,0.4)] text-[#f08984]'
              : banner.type === 'success'
                ? 'border-[rgba(62,207,155,0.4)] text-[#3ecf9b]'
                : 'border-[rgba(94,200,242,0.35)] text-[#5ec8f2]'
          }`}
        >
          {banner.message}
        </div>
      )}

      <div className="ctx-shell p-5 sm:p-6">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-semibold text-[#e8edf4]">{selectedName}</p>
            <p className="mt-1 text-xs text-[#8b9cb0]">
              {studio?.approved_ontology_version_id
                ? `Approved ontology ${studio.approved_ontology_version_id}`
                : 'No approved ontology on this fabric yet'}
            </p>
          </div>
          <div className="grid grid-cols-4 gap-2 text-center">
            {[
              ['Turns', counts?.episodes ?? 0],
              ['Queue', counts?.queued ?? 0],
              ['Overrides', counts?.overrides ?? 0],
              ['Gaps', counts?.gaps ?? 0],
            ].map(([label, value]) => (
              <div key={String(label)} className="min-w-[4.5rem] rounded-xl border border-[rgba(148,163,184,0.14)] px-3 py-2">
                <p className="text-lg font-semibold text-[#e8edf4]">{value}</p>
                <p className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">{label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="mb-5 flex flex-wrap gap-2">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`ctx-tab ${tab === item.id ? 'is-active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <p className="mb-4 text-sm text-[#8b9cb0]">{TABS.find((item) => item.id === tab)?.hint}</p>

        {loadingStudio && <p className="text-sm text-[#8b9cb0]">Reading the context layer…</p>}

        {!loadingStudio && tab === 'in-use' && (
          <div className="space-y-3">
            {(studio?.episodes || []).length === 0 && (
              <Empty icon={MagnifyingGlassIcon} title="No turns yet" body="Ask this fabric a question. The envelope for that answer will appear here." />
            )}
            {(studio?.episodes || []).map((episode) => {
              const lines = episode.context_envelope?.lines || [];
              const open = openEpisode === episode.id;
              return (
                <article key={episode.id} className="ctx-card">
                  <button type="button" className="w-full text-left" onClick={() => setOpenEpisode(open ? null : episode.id)}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="ctx-kind ontology">{episode.context_envelope?.route || episode.route || 'turn'}</span>
                      <span className="text-xs text-[#8b9cb0]">{confidenceLabel(episode.confidence ?? episode.context_envelope?.confidence)}</span>
                      <span className="text-xs text-[#8b9cb0]">{lines.length} lines</span>
                    </div>
                    <h3 className="mt-2 text-base font-medium text-[#e8edf4]">{episode.query}</h3>
                    <p className="mt-1 line-clamp-2 text-sm text-[#cbd5e1]">{episode.answer}</p>
                  </button>
                  {open && (
                    <div className="mt-4 space-y-3 border-t border-[rgba(148,163,184,0.12)] pt-4">
                      {lines.length === 0 && <p className="text-sm text-[#8b9cb0]">This turn was recorded before envelopes were stored.</p>}
                      {lines.map((line, index) => (
                        <ContextEvidenceBubble
                          key={`${episode.id}-${index}`}
                          line={line}
                          index={index}
                        />
                      ))}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}

        {!loadingStudio && tab === 'queue' && (
          <div className="space-y-3">
            {(studio?.queue || []).length === 0 && (
              <Empty icon={SparklesIcon} title="Queue is clear" body="A correction from an answer lands here until you accept it as memory or as an ontology draft." />
            )}
            {(studio?.queue || []).map((candidate) => (
              <article key={candidate.id} className="ctx-card">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="ctx-kind memory">{destinationLabel[candidate.destination || 'memory'] || candidate.destination}</span>
                  {candidate.episode_id && <span className="font-mono text-[11px] text-[#8b9cb0]">{candidate.episode_id}</span>}
                </div>
                <p className="mt-2 text-sm text-[#e8edf4]">{candidate.proposed_fact}</p>
                {candidate.query && <p className="mt-1 text-xs text-[#8b9cb0]">From: {candidate.query}</p>}
                {candidate.classification_reason && <p className="mt-2 text-xs text-[#5ec8f2]">{candidate.classification_reason}</p>}
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() => act(`api/v1/agent/enrichment/${candidate.id}/approve`, 'Correction applied. A rule or alias waits on the ontology draft until that version is approved.')}
                    className="inline-flex items-center gap-1 rounded-lg border border-[rgba(62,207,155,0.4)] px-3 py-1.5 text-xs text-[#3ecf9b]"
                  >
                    <CheckIcon className="h-3.5 w-3.5" /> Accept
                  </button>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() => act(`api/v1/agent/enrichment/${candidate.id}/reject`, 'Correction rejected.')}
                    className="inline-flex items-center gap-1 rounded-lg border border-[rgba(240,137,132,0.4)] px-3 py-1.5 text-xs text-[#f08984]"
                  >
                    <XMarkIcon className="h-3.5 w-3.5" /> Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        {!loadingStudio && tab === 'overrides' && (
          <div className="space-y-3">
            {(studio?.overrides || []).length === 0 && (
              <Empty icon={SparklesIcon} title="No active overrides" body="Approved value corrections show here. They change the next answer and leave the source table alone." />
            )}
            {(studio?.overrides || []).map((fact) => (
              <article key={fact.candidate_id || fact.fact} className="ctx-card">
                <span className="ctx-kind memory">Override</span>
                <p className="mt-2 text-sm text-[#e8edf4]">{fact.fact}</p>
                {fact.query && <p className="mt-1 text-xs text-[#8b9cb0]">Asked as: {fact.query}</p>}
                {fact.candidate_id && (
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      disabled={busyId !== null}
                      onClick={() => act(
                        `api/v1/agent/fabrics/${encodeURIComponent(fabricId)}/memory/${encodeURIComponent(fact.candidate_id || '')}/promote`,
                        'Proposed to the ontology draft. The override still applies until that version is approved.'
                      )}
                      className="rounded-lg border border-[rgba(94,200,242,0.4)] px-3 py-1.5 text-xs text-[#5ec8f2]"
                    >
                      Promote to ontology
                    </button>
                    <button
                      type="button"
                      disabled={busyId !== null}
                      onClick={() => act(
                        `api/v1/agent/fabrics/${encodeURIComponent(fabricId)}/memory/${encodeURIComponent(fact.candidate_id || '')}/retire`,
                        'Override retired. Later answers use the source again.'
                      )}
                      className="rounded-lg border border-[rgba(148,163,184,0.3)] px-3 py-1.5 text-xs text-[#8b9cb0]"
                    >
                      Retire
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}

        {!loadingStudio && tab === 'coverage' && (
          <div className="space-y-3">
            {(studio?.coverage || []).length === 0 && (
              <Empty icon={MagnifyingGlassIcon} title="No gaps in this window" body="Every stored turn had an ontology line and evidence from the table, a passage, or the graph." />
            )}
            {(studio?.coverage || []).map((gap) => (
              <article key={gap.query} className="ctx-card">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`ctx-kind ${gap.gap === 'no_ontology' ? 'ontology' : 'passage'}`}>
                    {gap.gap === 'no_ontology' ? 'No ontology name' : 'Named, no evidence'}
                  </span>
                  <span className="text-xs text-[#8b9cb0]">{gap.count} {gap.count === 1 ? 'ask' : 'asks'}</span>
                  {gap.route && <span className="text-xs text-[#8b9cb0]">{gap.route}</span>}
                  <span className="text-xs text-[#8b9cb0]">{confidenceLabel(gap.confidence)}</span>
                </div>
                <h3 className="mt-2 text-base text-[#e8edf4]">{gap.query}</h3>
                <p className="mt-1 text-sm text-[#8b9cb0]">
                  {gap.gap === 'no_ontology'
                    ? 'The envelope had evidence, and the approved ontology did not name the subject.'
                    : 'The ontology named the subject, and the fabric returned no table row, passage, or graph fact.'}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

function Empty({ icon: Icon, title, body }: { icon: React.ComponentType<{ className?: string }>; title: string; body: string }) {
  return (
    <div className="ctx-card flex items-start gap-3">
      <Icon className="mt-0.5 h-5 w-5 text-[#5ec8f2]" />
      <div>
        <p className="font-medium text-[#e8edf4]">{title}</p>
        <p className="mt-1 text-sm text-[#8b9cb0]">{body}</p>
      </div>
    </div>
  );
}

export default ContextAnalysis;
