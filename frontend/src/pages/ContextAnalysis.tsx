import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowPathIcon,
  CheckIcon,
  ClipboardDocumentIcon,
  LinkIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  SparklesIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';
import ContextEvidenceBubble from '../components/ContextEvidenceBubble';

type ModeId = 'design' | 'prove' | 'attach';
type ProveTab = 'in-use' | 'queue' | 'overrides' | 'coverage';

interface FabricOption {
  id: string;
  name: string;
  status?: string;
  approved_ontology_version_id?: string | null;
  ontology_project_id?: string | null;
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
    context_id?: string | null;
    context_name?: string | null;
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

interface ContextProfile {
  id: string;
  name: string;
  status: string;
  version: number;
  purpose: string;
  primary_fabric_id?: string | null;
  fabric_name?: string;
  fabric_ids?: string[];
  ontology_version_id?: string | null;
  ontology_project_id?: string | null;
  scope?: {
    collections?: string[];
    entity_types?: string[];
    exclude_collections?: string[];
  };
  rules?: Array<{ id?: string; text: string; severity?: string } | string>;
  playbook?: {
    routes?: string[];
    default_route?: string;
    notes?: string;
  };
  evidence_policy?: {
    require_table_or_passage?: boolean;
    prefer_kinds?: string[];
    fail_closed?: boolean;
  };
  decision_schema?: {
    keys?: string[];
    decisions?: string[];
    human_review_if_confidence_below?: number;
    require_evidence?: boolean;
  };
  memory_notes?: Array<{ text: string } | string>;
  agent_bindings?: Array<{ agent_key: string; label?: string; bound_at?: string }>;
  updated_at?: string;
  published_at?: string | null;
  agent_snippet?: string;
  preamble_preview?: string;
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
  profiles?: ContextProfile[];
}

const PROVE_TABS: { id: ProveTab; label: string; hint: string }[] = [
  { id: 'in-use', label: 'In use', hint: 'Envelope each answer used under this fabric (and context when attached)' },
  { id: 'queue', label: 'Queue', hint: 'Corrections waiting for a destination' },
  { id: 'overrides', label: 'Overrides', hint: 'Memory that stands in for the source' },
  { id: 'coverage', label: 'Coverage', hint: 'Questions the contract or evidence could not carry' },
];

const AGENT_PRESETS = [
  { key: 'claims_audit', label: 'Claims & Billing Audit' },
  { key: 'eligibility', label: 'Eligibility Verification' },
  { key: 'care_coordination', label: 'Care Coordination' },
  { key: 'duplicate_routing', label: 'Duplicate Decision Routing' },
  { key: 'risk', label: 'Risk Stratification' },
  { key: 'custom', label: 'Custom agent' },
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

function rulesToText(rules: ContextProfile['rules']): string {
  if (!rules?.length) return '';
  return rules
    .map((r) => (typeof r === 'string' ? r : `${r.severity || 'info'}: ${r.text || ''}`))
    .join('\n');
}

function textToRules(text: string): Array<{ id: string; text: string; severity: string }> {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, i) => {
      const m = line.match(/^(info|warn|critical)\s*:\s*(.+)$/i);
      if (m) return { id: `rule_${i}`, severity: m[1].toLowerCase(), text: m[2] };
      return { id: `rule_${i}`, severity: 'info', text: line };
    });
}

function notesToText(notes: ContextProfile['memory_notes']): string {
  if (!notes?.length) return '';
  return notes.map((n) => (typeof n === 'string' ? n : n.text || '')).filter(Boolean).join('\n');
}

function textToNotes(text: string): Array<{ text: string }> {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => ({ text: line }));
}

const ContextAnalysis: React.FC = () => {
  const [fabrics, setFabrics] = useState<FabricOption[]>([]);
  const [fabricId, setFabricId] = useState('');
  const [studio, setStudio] = useState<Studio | null>(null);
  const [profiles, setProfiles] = useState<ContextProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ContextProfile | null>(null);
  const [mode, setMode] = useState<ModeId>('design');
  const [proveTab, setProveTab] = useState<ProveTab>('in-use');
  const [openEpisode, setOpenEpisode] = useState<string | null>(null);
  const [loadingFabrics, setLoadingFabrics] = useState(true);
  const [loadingStudio, setLoadingStudio] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);
  const [newName, setNewName] = useState('Claims adjudication context');
  const [bindKey, setBindKey] = useState(AGENT_PRESETS[0].key);
  const [bindLabel, setBindLabel] = useState(AGENT_PRESETS[0].label);
  const [snippet, setSnippet] = useState('');
  const [preamble, setPreamble] = useState('');

  const selectedName = useMemo(
    () => fabrics.find((f) => f.id === fabricId)?.name || studio?.fabric_name || 'Select a fabric',
    [fabrics, fabricId, studio]
  );

  const loadProfiles = useCallback(async (fid?: string) => {
    const q = fid ? `?fabric_id=${encodeURIComponent(fid)}` : '';
    const response = await apiRequest(`api/v1/agent/context-profiles${q}`);
    const payload = await response.json();
    const rows = (payload.data?.profiles || []) as ContextProfile[];
    setProfiles(rows);
    return rows;
  }, []);

  const loadProfileDetail = useCallback(async (id: string) => {
    const response = await apiRequest(`api/v1/agent/context-profiles/${encodeURIComponent(id)}`);
    const payload = await response.json();
    if (!payload.success) throw new Error(payload.message || 'Failed to load context');
    const profile = payload.data as ContextProfile;
    setDraft(profile);
    setSelectedId(profile.id);
    setSnippet(profile.agent_snippet || '');
    setPreamble(profile.preamble_preview || '');
    return profile;
  }, []);

  const loadStudio = useCallback(async (id: string) => {
    if (!id) return;
    setLoadingStudio(true);
    try {
      const response = await apiRequest(`api/v1/agent/fabrics/${encodeURIComponent(id)}/context`);
      const payload = await response.json();
      if (!payload.success) throw new Error(payload.message || 'Context studio failed');
      const data = payload.data as Studio;
      setStudio(data);
      const rows = data.profiles?.length ? data.profiles : await loadProfiles(id);
      setProfiles(rows);
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
  }, [loadProfiles]);

  useEffect(() => {
    const load = async () => {
      setLoadingFabrics(true);
      try {
        const response = await apiRequest('api/v1/knowledge/');
        const payload = await response.json();
        const rows = Array.isArray(payload.data) ? payload.data : [];
        setFabrics(
          rows.map((row: FabricOption) => ({
            id: row.id,
            name: row.name,
            status: row.status,
            approved_ontology_version_id: row.approved_ontology_version_id,
            ontology_project_id: row.ontology_project_id,
          }))
        );
        setFabricId((current) => current || rows[0]?.id || '');
      } catch {
        setBanner({ type: 'error', message: 'Unable to load fabrics. Confirm the API is running.' });
      } finally {
        setLoadingFabrics(false);
      }
    };
    load();
  }, []);

  useEffect(() => {
    if (fabricId) {
      loadStudio(fabricId);
      setSelectedId(null);
      setDraft(null);
      setSnippet('');
      setPreamble('');
    }
  }, [fabricId, loadStudio]);

  const createProfile = async () => {
    if (!fabricId) return;
    setBusy(true);
    try {
      const fabric = fabrics.find((f) => f.id === fabricId);
      const response = await apiRequest('api/v1/agent/context-profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName || 'Untitled context',
          fabric_id: fabricId,
          fabric_name: fabric?.name || '',
          purpose: 'Operating contract between the knowledge fabric and agents for this domain.',
          ontology_version_id: fabric?.approved_ontology_version_id || studio?.approved_ontology_version_id || null,
          ontology_project_id: fabric?.ontology_project_id || studio?.ontology_project_id || null,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Create failed');
      }
      setBanner({ type: 'success', message: 'Context layer created — attach rules, then publish for agents.' });
      await loadStudio(fabricId);
      await loadProfileDetail(payload.data.id);
      setMode('design');
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Create failed' });
    } finally {
      setBusy(false);
    }
  };

  const saveDraft = async () => {
    if (!draft?.id) return;
    setBusy(true);
    try {
      const response = await apiRequest(`api/v1/agent/context-profiles/${encodeURIComponent(draft.id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: draft.name,
          purpose: draft.purpose,
          fabric_id: fabricId,
          fabric_name: selectedName,
          ontology_version_id: draft.ontology_version_id,
          ontology_project_id: draft.ontology_project_id,
          scope: draft.scope,
          rules: draft.rules,
          playbook: draft.playbook,
          evidence_policy: draft.evidence_policy,
          decision_schema: draft.decision_schema,
          memory_notes: draft.memory_notes,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Save failed');
      }
      setBanner({ type: 'success', message: 'Context layer saved.' });
      await loadStudio(fabricId);
      await loadProfileDetail(draft.id);
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const publishProfile = async () => {
    if (!draft?.id) return;
    await saveDraft();
    setBusy(true);
    try {
      const response = await apiRequest(`api/v1/agent/context-profiles/${encodeURIComponent(draft.id)}/publish`, {
        method: 'POST',
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Publish failed');
      }
      setBanner({ type: 'success', message: 'Context layer published — agents can attach this version.' });
      await loadStudio(fabricId);
      await loadProfileDetail(draft.id);
      setMode('attach');
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Publish failed' });
    } finally {
      setBusy(false);
    }
  };

  const deleteProfile = async (id: string) => {
    if (!window.confirm('Delete this context layer? Agents using it will lose the contract.')) return;
    setBusy(true);
    try {
      const response = await apiRequest(`api/v1/agent/context-profiles/${encodeURIComponent(id)}`, { method: 'DELETE' });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Delete failed');
      }
      if (selectedId === id) {
        setSelectedId(null);
        setDraft(null);
        setSnippet('');
        setPreamble('');
      }
      setBanner({ type: 'success', message: 'Context layer deleted.' });
      await loadStudio(fabricId);
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Delete failed' });
    } finally {
      setBusy(false);
    }
  };

  const bindAgent = async () => {
    if (!draft?.id) return;
    setBusy(true);
    try {
      const key = bindKey === 'custom' ? `custom_${Date.now().toString(36)}` : bindKey;
      const response = await apiRequest(`api/v1/agent/context-profiles/${encodeURIComponent(draft.id)}/bind-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_key: key, label: bindLabel || key }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Bind failed');
      }
      setBanner({ type: 'success', message: `Bound ${bindLabel || key} to this context layer.` });
      await loadProfileDetail(draft.id);
      await loadStudio(fabricId);
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Bind failed' });
    } finally {
      setBusy(false);
    }
  };

  const unbindAgent = async (agentKey: string) => {
    if (!draft?.id) return;
    setBusy(true);
    try {
      const response = await apiRequest(`api/v1/agent/context-profiles/${encodeURIComponent(draft.id)}/unbind-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_key: agentKey }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.detail || payload.message || 'Unbind failed');
      }
      await loadProfileDetail(draft.id);
    } catch (error) {
      setBanner({ type: 'error', message: error instanceof Error ? error.message : 'Unbind failed' });
    } finally {
      setBusy(false);
    }
  };

  const copySnippet = async () => {
    if (!snippet) return;
    try {
      await navigator.clipboard.writeText(snippet);
      setBanner({ type: 'success', message: 'Agent attach snippet copied.' });
    } catch {
      setBanner({ type: 'info', message: 'Copy manually from the snippet box.' });
    }
  };

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

  const counts = studio?.counts;
  const collectionsText = (draft?.scope?.collections || []).join(', ');
  const routesText = (draft?.playbook?.routes || []).join(', ');

  return (
    <div className="ctx-studio mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[#5ec8f2]">Between fabric and agents</p>
          <h1 className="mt-1 text-3xl font-semibold text-[#e8edf4]">Context Layer</h1>
          <p className="mt-2 max-w-2xl text-sm text-[#8b9cb0]">
            Design a scientific operating contract on top of a Knowledge Fabric—scope, ontology lens, rules, playbook—then attach it to agents. Prove each answer against that contract.
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

      <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {[
          ['1 · Fabric', selectedName, 'Measured knowledge asset'],
          ['2 · Context Layer', draft?.name || 'Not selected', draft ? `${draft.status} · v${draft.version}` : 'Design on top of the fabric'],
          ['3 · Agents', `${draft?.agent_bindings?.length || 0} bound`, 'Query with fabric_id + context_id'],
        ].map(([step, title, sub]) => (
          <div key={String(step)} className="rounded-2xl border border-[rgba(148,163,184,0.16)] bg-white/[0.03] px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">{step}</p>
            <p className="mt-1 truncate text-sm font-semibold text-[#e8edf4]">{title}</p>
            <p className="mt-0.5 text-xs text-[#8b9cb0]">{sub}</p>
          </div>
        ))}
      </div>

      <div className="ctx-shell p-5 sm:p-6">
        <div className="mb-5 flex flex-wrap gap-2">
          {(
            [
              ['design', 'Design'],
              ['prove', 'Prove'],
              ['attach', 'Attach to agents'],
            ] as Array<[ModeId, string]>
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`ctx-tab ${mode === id ? 'is-active' : ''}`}
              onClick={() => setMode(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === 'design' && (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            <aside className="lg:col-span-4 space-y-3">
              <div className="rounded-2xl border border-dashed border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.06)] p-3">
                <p className="text-xs font-medium text-[#bfeaff]">New context on this fabric</p>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="mt-2 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                  placeholder="e.g. Claims adjudication context"
                />
                <button
                  type="button"
                  disabled={busy || !fabricId}
                  onClick={createProfile}
                  className="mt-2 inline-flex w-full items-center justify-center gap-1 rounded-xl border border-[rgba(62,207,155,0.45)] bg-[rgba(62,207,155,0.12)] px-3 py-2 text-sm text-[#3ecf9b]"
                >
                  <PlusIcon className="h-4 w-4" /> Create & attach fabric
                </button>
              </div>

              <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Profiles on fabric</p>
              {profiles.length === 0 && (
                <p className="text-sm text-[#8b9cb0]">No context layers yet. Create one to sit between this fabric and your agents.</p>
              )}
              {profiles.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => loadProfileDetail(p.id)}
                  className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${
                    selectedId === p.id
                      ? 'border-[rgba(94,200,242,0.55)] bg-[rgba(94,200,242,0.12)]'
                      : 'border-[rgba(148,163,184,0.16)] bg-white/[0.03] hover:border-[rgba(94,200,242,0.35)]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-[#e8edf4]">{p.name}</span>
                    <span className={`ctx-kind ${p.status === 'published' ? 'table' : 'session'}`}>{p.status}</span>
                  </div>
                  <p className="mt-1 text-[11px] text-[#8b9cb0]">v{p.version} · {(p.agent_bindings || []).length} agents</p>
                </button>
              ))}
            </aside>

            <section className="lg:col-span-8">
              {!draft && (
                <Empty
                  icon={SparklesIcon}
                  title="Design the layer agents must honor"
                  body="Attach this fabric, add purpose, scope, rules, decision playbook, and steward notes beyond the rows. Publish, then bind agents with fabric_id + context_id."
                />
              )}
              {draft && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <input
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                        className="w-full max-w-md rounded-xl border border-[rgba(148,163,184,0.2)] bg-transparent px-0 py-1 text-xl font-semibold text-[#e8edf4] outline-none"
                      />
                      <p className="mt-1 font-mono text-[11px] text-[#8b9cb0]">{draft.id}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button type="button" disabled={busy} onClick={saveDraft} className="rounded-xl border border-[rgba(94,200,242,0.4)] px-3 py-1.5 text-xs text-[#5ec8f2]">
                        Save
                      </button>
                      <button type="button" disabled={busy} onClick={publishProfile} className="rounded-xl border border-[rgba(62,207,155,0.45)] bg-[rgba(62,207,155,0.12)] px-3 py-1.5 text-xs text-[#3ecf9b]">
                        Publish
                      </button>
                      <button type="button" disabled={busy} onClick={() => deleteProfile(draft.id)} className="rounded-xl border border-[rgba(240,137,132,0.4)] px-3 py-1.5 text-xs text-[#f08984]">
                        <TrashIcon className="inline h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <label className="block">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Purpose</span>
                    <textarea
                      value={draft.purpose || ''}
                      onChange={(e) => setDraft({ ...draft, purpose: e.target.value })}
                      rows={2}
                      className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                    />
                  </label>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Ontology version lens</span>
                      <input
                        value={draft.ontology_version_id || ''}
                        onChange={(e) => setDraft({ ...draft, ontology_version_id: e.target.value || null })}
                        placeholder={studio?.approved_ontology_version_id || 'optional'}
                        className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 font-mono text-xs text-[#e8edf4]"
                      />
                    </label>
                    <label className="block">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Scope collections (comma-separated, empty = all)</span>
                      <input
                        value={collectionsText}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            scope: {
                              ...(draft.scope || {}),
                              collections: e.target.value
                                .split(',')
                                .map((s) => s.trim())
                                .filter(Boolean),
                            },
                          })
                        }
                        placeholder="claims, members, plans"
                        className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                      />
                    </label>
                  </div>

                  <label className="block">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Business rules (one per line; optional severity: info|warn|critical:)</span>
                    <textarea
                      value={rulesToText(draft.rules)}
                      onChange={(e) => setDraft({ ...draft, rules: textToRules(e.target.value) })}
                      rows={4}
                      placeholder={'critical: Missing prior auth on MRI → human_review\ninfo: Prefer claim_id + plan_id in evidence'}
                      className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 font-mono text-xs text-[#e8edf4]"
                    />
                  </label>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Playbook routes</span>
                      <input
                        value={routesText}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            playbook: {
                              ...(draft.playbook || {}),
                              routes: e.target.value
                                .split(',')
                                .map((s) => s.trim())
                                .filter(Boolean),
                            },
                          })
                        }
                        className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                      />
                    </label>
                    <label className="block">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Default route</span>
                      <input
                        value={draft.playbook?.default_route || 'human_review'}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            playbook: { ...(draft.playbook || {}), default_route: e.target.value },
                          })
                        }
                        className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                      />
                    </label>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="flex items-center gap-2 rounded-xl border border-[rgba(148,163,184,0.16)] px-3 py-2 text-sm text-[#cbd5e1]">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.evidence_policy?.fail_closed)}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            evidence_policy: { ...(draft.evidence_policy || {}), fail_closed: e.target.checked },
                          })
                        }
                      />
                      Fail closed (no invent without evidence)
                    </label>
                    <label className="block">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Human review if confidence below</span>
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        value={draft.decision_schema?.human_review_if_confidence_below ?? 0.7}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            decision_schema: {
                              ...(draft.decision_schema || {}),
                              human_review_if_confidence_below: Number(e.target.value),
                            },
                          })
                        }
                        className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                      />
                    </label>
                  </div>

                  <label className="block">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Steward notes (context beyond source rows)</span>
                    <textarea
                      value={notesToText(draft.memory_notes)}
                      onChange={(e) => setDraft({ ...draft, memory_notes: textToNotes(e.target.value) })}
                      rows={3}
                      placeholder="C-SNP demo: treat PLN_CSNP members as chronic-SNP pathway for adjudication assists."
                      className="mt-1 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                    />
                  </label>

                  <div className="rounded-2xl border border-[rgba(148,163,184,0.16)] bg-black/20 p-3">
                    <p className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Attached fabric</p>
                    <p className="mt-1 text-sm text-[#e8edf4]">{selectedName}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-[#8b9cb0]">{draft.primary_fabric_id || fabricId}</p>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}

        {mode === 'attach' && (
          <div className="space-y-4">
            {!draft && (
              <Empty icon={LinkIcon} title="Select or create a context layer first" body="Design tab → create profile on this fabric → publish → return here to bind agents." />
            )}
            {draft && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`ctx-kind ${draft.status === 'published' ? 'table' : 'session'}`}>{draft.status}</span>
                  <span className="text-sm text-[#e8edf4]">{draft.name}</span>
                  <span className="text-xs text-[#8b9cb0]">v{draft.version}</span>
                </div>

                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <div className="rounded-2xl border border-[rgba(148,163,184,0.16)] p-4">
                    <p className="text-sm font-semibold text-[#e8edf4]">Bind an agent</p>
                    <p className="mt-1 text-xs text-[#8b9cb0]">Agents call the fabric with this context_id so they inherit the designed contract.</p>
                    <select
                      value={bindKey}
                      onChange={(e) => {
                        const preset = AGENT_PRESETS.find((p) => p.key === e.target.value);
                        setBindKey(e.target.value);
                        if (preset && preset.key !== 'custom') setBindLabel(preset.label);
                      }}
                      className="mt-3 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                    >
                      {AGENT_PRESETS.map((p) => (
                        <option key={p.key} value={p.key}>{p.label}</option>
                      ))}
                    </select>
                    <input
                      value={bindLabel}
                      onChange={(e) => setBindLabel(e.target.value)}
                      className="mt-2 w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#0b0f16] px-3 py-2 text-sm text-[#e8edf4]"
                      placeholder="Agent display label"
                    />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={bindAgent}
                      className="mt-3 inline-flex items-center gap-1 rounded-xl border border-[rgba(62,207,155,0.45)] bg-[rgba(62,207,155,0.12)] px-3 py-2 text-sm text-[#3ecf9b]"
                    >
                      <LinkIcon className="h-4 w-4" /> Bind to context + fabric
                    </button>

                    <div className="mt-4 space-y-2">
                      {(draft.agent_bindings || []).length === 0 && (
                        <p className="text-xs text-[#8b9cb0]">No agents bound yet.</p>
                      )}
                      {(draft.agent_bindings || []).map((b) => (
                        <div key={b.agent_key} className="flex items-center justify-between rounded-xl border border-[rgba(148,163,184,0.14)] px-3 py-2">
                          <div>
                            <p className="text-sm text-[#e8edf4]">{b.label || b.agent_key}</p>
                            <p className="font-mono text-[10px] text-[#8b9cb0]">{b.agent_key}</p>
                          </div>
                          <button type="button" onClick={() => unbindAgent(b.agent_key)} className="text-xs text-[#f08984]">
                            Unbind
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-[rgba(148,163,184,0.16)] p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[#e8edf4]">Agent attach snippet</p>
                      <button type="button" onClick={copySnippet} className="inline-flex items-center gap-1 text-xs text-[#5ec8f2]">
                        <ClipboardDocumentIcon className="h-4 w-4" /> Copy
                      </button>
                    </div>
                    <pre className="mt-3 max-h-56 overflow-auto rounded-xl border border-[rgba(148,163,184,0.14)] bg-[#070b12] p-3 font-mono text-[11px] text-[#bfeaff] whitespace-pre-wrap">
                      {snippet || 'Save/open a profile to generate the snippet.'}
                    </pre>
                    <p className="mt-3 text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Preamble agents will receive</p>
                    <pre className="mt-2 max-h-40 overflow-auto rounded-xl border border-[rgba(148,163,184,0.14)] bg-[#070b12] p-3 font-mono text-[10px] text-[#9fb0c5] whitespace-pre-wrap">
                      {preamble || '—'}
                    </pre>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {mode === 'prove' && (
          <>
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-lg font-semibold text-[#e8edf4]">{selectedName}</p>
                <p className="mt-1 text-xs text-[#8b9cb0]">
                  {studio?.approved_ontology_version_id
                    ? `Approved ontology ${studio.approved_ontology_version_id}`
                    : 'No approved ontology on this fabric yet'}
                  {draft ? ` · proving under context ${draft.name}` : ''}
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
              {PROVE_TABS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`ctx-tab ${proveTab === item.id ? 'is-active' : ''}`}
                  onClick={() => setProveTab(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <p className="mb-4 text-sm text-[#8b9cb0]">{PROVE_TABS.find((item) => item.id === proveTab)?.hint}</p>

            {loadingStudio && <p className="text-sm text-[#8b9cb0]">Reading the context layer…</p>}

            {!loadingStudio && proveTab === 'in-use' && (
              <div className="space-y-3">
                {(studio?.episodes || []).length === 0 && (
                  <Empty icon={MagnifyingGlassIcon} title="No turns yet" body="Ask this fabric with context_id set. The envelope for that answer will appear here." />
                )}
                {(studio?.episodes || []).map((episode) => {
                  const lines = episode.context_envelope?.lines || [];
                  const open = openEpisode === episode.id;
                  return (
                    <article key={episode.id} className="ctx-card">
                      <button type="button" className="w-full text-left" onClick={() => setOpenEpisode(open ? null : episode.id)}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="ctx-kind ontology">{episode.context_envelope?.route || episode.route || 'turn'}</span>
                          {episode.context_envelope?.context_id && (
                            <span className="ctx-kind memory">{episode.context_envelope.context_name || episode.context_envelope.context_id}</span>
                          )}
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
                            <ContextEvidenceBubble key={`${episode.id}-${index}`} line={line} index={index} />
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}

            {!loadingStudio && proveTab === 'queue' && (
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
                        onClick={() => act(`api/v1/agent/enrichment/${candidate.id}/approve`, 'Correction applied.')}
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

            {!loadingStudio && proveTab === 'overrides' && (
              <div className="space-y-3">
                {(studio?.overrides || []).length === 0 && (
                  <Empty icon={SparklesIcon} title="No active overrides" body="Approved value corrections show here." />
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
                          onClick={() =>
                            act(
                              `api/v1/agent/fabrics/${encodeURIComponent(fabricId)}/memory/${encodeURIComponent(fact.candidate_id || '')}/promote`,
                              'Proposed to the ontology draft.'
                            )
                          }
                          className="rounded-lg border border-[rgba(94,200,242,0.4)] px-3 py-1.5 text-xs text-[#5ec8f2]"
                        >
                          Promote to ontology
                        </button>
                        <button
                          type="button"
                          disabled={busyId !== null}
                          onClick={() =>
                            act(
                              `api/v1/agent/fabrics/${encodeURIComponent(fabricId)}/memory/${encodeURIComponent(fact.candidate_id || '')}/retire`,
                              'Override retired.'
                            )
                          }
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

            {!loadingStudio && proveTab === 'coverage' && (
              <div className="space-y-3">
                {(studio?.coverage || []).length === 0 && (
                  <Empty icon={MagnifyingGlassIcon} title="No gaps in this window" body="Every stored turn had ontology and evidence coverage." />
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
                  </article>
                ))}
              </div>
            )}
          </>
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
