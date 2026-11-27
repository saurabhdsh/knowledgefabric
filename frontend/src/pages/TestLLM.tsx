import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpIcon,
  CheckCircleIcon,
  LinkIcon,
  SparklesIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';
import { renderLlmMarkdown } from '../utils/renderLlmGraphInsight';
import { fabricKindLabel } from '../utils/weaveDomain';

interface KnowledgeFabric {
  id: string;
  name: string;
  status: string;
  document_count: number;
  total_chunks?: number;
  created_at: string;
  model_status: string;
  weave_domain?: string;
  fabric_kind_label?: string;
}

interface PublishedContext {
  id: string;
  name: string;
  status: string;
  version: number;
  purpose?: string;
  primary_fabric_id?: string | null;
  playbook?: { routes?: string[]; default_route?: string };
  agent_bindings?: Array<{ agent_key: string; label?: string }>;
}

type TestResult = {
  fabricId: string;
  llmProvider: string;
  query: string;
  response: string;
  confidence: number;
  timestamp: string;
  relevantChunks: number;
  packedChunks?: number;
  processingTime: string;
  sessionId?: string;
  episodeId?: string;
  contextId?: string;
  contextName?: string;
  route?: string;
  decision?: string;
  decisionResolver?: string;
  feedbackState?: string | null;
};

function shortRecordId(value?: string): string {
  const id = String(value || '').trim();
  if (!id) return '';
  if (id.length <= 18) return id;
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

function splitScientificSections(markdown: string): Array<{ title: string; body: string }> {
  const text = String(markdown || '').trim();
  if (!text) return [];
  const parts = text.split(/\n(?=##\s+)/);
  if (parts.length <= 1 && !/^##\s+/m.test(text)) {
    return [{ title: 'Answer', body: text }];
  }
  return parts
    .map((block) => {
      const lines = block.trim().split('\n');
      const head = lines[0] || '';
      const title = head.replace(/^#+\s*/, '').trim() || 'Section';
      const body = lines.slice(1).join('\n').trim();
      return { title, body: body || head.replace(/^#+\s*/, '').trim() };
    })
    .filter((s) => s.body);
}

function decisionTone(decision?: string): string {
  const d = String(decision || '').toLowerCase();
  if (d === 'pay') return 'bg-[rgba(62,207,155,0.12)] text-[#9af0ca] border-[rgba(62,207,155,0.35)]';
  if (d === 'deny') return 'bg-[rgba(240,137,132,0.12)] text-[#f3b4b0] border-[rgba(240,137,132,0.35)]';
  if (d === 'hold') return 'bg-[rgba(251,191,36,0.12)] text-[#fcd34d] border-[rgba(251,191,36,0.35)]';
  if (d === 'human_review') return 'bg-[rgba(155,139,212,0.14)] text-[#d7cff5] border-[rgba(155,139,212,0.35)]';
  return 'bg-white/[0.06] text-[#cbd5e1] border-[rgba(148,163,184,0.2)]';
}

const ScientificAnswer: React.FC<{ markdown: string; decision?: string }> = ({ markdown, decision }) => {
  const sections = splitScientificSections(markdown);
  return (
    <div className="space-y-3">
      {sections.map((section) => {
        const isDecision = /^decision$/i.test(section.title);
        return (
          <div
            key={`${section.title}-${section.body.slice(0, 24)}`}
            className={`rounded-2xl border px-4 py-3 ${
              isDecision
                ? 'border-[rgba(94,200,242,0.28)] bg-[linear-gradient(160deg,rgba(94,200,242,0.1),rgba(16,20,29,0.55))]'
                : 'border-[rgba(148,163,184,0.12)] bg-[#0b0f16]/55'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b9cb0]">
                {section.title}
              </p>
              {isDecision && decision && (
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${decisionTone(decision)}`}>
                  {decision}
                </span>
              )}
            </div>
            <div className="mt-2 text-[14px] leading-[1.65] text-[#e8edf4]">
              {renderLlmMarkdown(section.body, 'dark')}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const TestLLM: React.FC = () => {
  const [selectedFabric, setSelectedFabric] = useState<string>('');
  const [selectedLLM, setSelectedLLM] = useState<string>('openai');
  const [llmProviders, setLlmProviders] = useState<Array<{ id: string; name: string; description?: string }>>([]);
  const [testQuery, setTestQuery] = useState<string>('');
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [sessionByFabric, setSessionByFabric] = useState<Record<string, string>>({});
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<number, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [loadingFabrics, setLoadingFabrics] = useState(true);
  const [statusBanner, setStatusBanner] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);
  const [contextProfiles, setContextProfiles] = useState<PublishedContext[]>([]);
  const [loadingContexts, setLoadingContexts] = useState(false);
  const [selectedContextId, setSelectedContextId] = useState<string>('');
  const [contextMode, setContextMode] = useState<'fabric' | 'layer'>('fabric');
  const [railOpen, setRailOpen] = useState(true);

  const transcriptRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const selectedContext = useMemo(
    () => contextProfiles.find((p) => p.id === selectedContextId) || null,
    [contextProfiles, selectedContextId]
  );

  const publishedContexts = useMemo(
    () => contextProfiles.filter((p) => p.status === 'published'),
    [contextProfiles]
  );

  const activeFabric = useMemo(
    () => fabrics.find((f) => f.id === selectedFabric) || null,
    [fabrics, selectedFabric]
  );

  const demoAdjudication = useMemo(() => {
    const fabric = fabrics.find((f) => f.id === selectedFabric);
    const hay = `${fabric?.id || ''} ${fabric?.name || ''}`.toLowerCase();
    const databricks =
      hay.includes('claims_demo')
      || hay.includes('claims_databricks')
      || hay.includes('databricks')
      || hay.includes('workspace_claims');
    if (databricks) {
      return {
        label: 'CLM_00004 · MBR_0004 · PLN_CSNP',
        query:
          'Should we pay claim CLM_00004 for member MBR_0004 on plan PLN_CSNP? Return a decision with rationale.',
        expectWithContext: 'hold',
        hint: 'Databricks claims_demo — CSNP + non-chronic M54.5 → hold',
      };
    }
    return {
      label: 'CLM-000008 · MEM-0004 · PLN-CSNP-SILVER',
      query:
        'Should we pay claim CLM-000008 for member MEM-0004 on plan PLN-CSNP-SILVER? Return a decision with rationale.',
      expectWithContext: 'pay',
      hint: 'Cost of Care — paid CSNP COPD-aligned claim → pay',
    };
  }, [fabrics, selectedFabric]);

  const loadContextsForFabric = useCallback(async (fabricId: string) => {
    if (!fabricId) {
      setContextProfiles([]);
      setSelectedContextId('');
      setContextMode('fabric');
      return;
    }
    setLoadingContexts(true);
    try {
      const response = await apiRequest(
        `api/v1/agent/context-profiles?fabric_id=${encodeURIComponent(fabricId)}`
      );
      const data = await response.json();
      const rows = ((data?.data?.profiles || []) as PublishedContext[]).filter(Boolean);
      setContextProfiles(rows);
      const published = rows.filter((p) => p.status === 'published');
      setSelectedContextId((prev) => {
        if (prev && published.some((p) => p.id === prev)) return prev;
        return '';
      });
      setContextMode((prev) => (prev === 'layer' && published.length === 0 ? 'fabric' : prev));
    } catch {
      setContextProfiles([]);
    } finally {
      setLoadingContexts(false);
    }
  }, []);

  useEffect(() => {
    const fetchFabrics = async () => {
      try {
        const response = await apiRequest('api/v1/knowledge/');
        const data = await response.json();
        if (data.success && data.data) {
          setFabrics(data.data);
          if (selectedFabric && !data.data.some((fabric: KnowledgeFabric) => fabric.id === selectedFabric)) {
            setSelectedFabric('');
            setStatusBanner({
              type: 'error',
              message: 'Previously selected fabric is no longer available. Please select another fabric.',
            });
          }
        } else {
          setStatusBanner({
            type: 'error',
            message: data.message || 'Unable to load knowledge fabrics.',
          });
        }
      } catch {
        setStatusBanner({
          type: 'error',
          message: 'Unable to load knowledge fabrics. Please check backend connectivity.',
        });
      } finally {
        setLoadingFabrics(false);
      }
    };

    fetchFabrics();

    const fetchProviders = async () => {
      try {
        const response = await apiRequest('api/v1/knowledge/api-keys/providers');
        const data = await response.json();
        const providers = data?.data?.providers || data?.providers || [];
        if (Array.isArray(providers) && providers.length > 0) {
          setLlmProviders(providers);
          setSelectedLLM(data?.data?.default_provider || providers[0].id);
        }
      } catch {
        /* keep default */
      }
    };
    fetchProviders();
  }, []);

  useEffect(() => {
    loadContextsForFabric(selectedFabric);
  }, [selectedFabric, loadContextsForFabric]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [testResults, isLoading]);

  const handleTestQuery = async () => {
    if (!selectedFabric) {
      setStatusBanner({ type: 'info', message: 'Select a knowledge fabric before running a test.' });
      return;
    }
    if (!testQuery.trim() || !selectedLLM) {
      setStatusBanner({ type: 'info', message: 'Enter a query to run a test.' });
      return;
    }
    if (contextMode === 'layer' && !selectedContextId) {
      setStatusBanner({ type: 'info', message: 'Pick a published Context Layer, or switch to Fabric only.' });
      return;
    }

    const pendingQuery = testQuery.trim();
    setIsLoading(true);
    setStatusBanner(null);

    try {
      const payload: Record<string, unknown> = {
        query: pendingQuery,
        llm_provider: selectedLLM,
        top_k: 8,
        session_id: sessionByFabric[selectedFabric] || undefined,
      };
      if (contextMode === 'layer' && selectedContextId) {
        payload.context_id = selectedContextId;
      }

      const response = await apiRequest(`api/v1/knowledge/query/${selectedFabric}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      const failure = !response.ok || data?.success === false;
      const detail = typeof data?.detail === 'string'
        ? data.detail
        : (data?.detail?.message || data?.error || data?.message);
      const answer = failure
        ? (detail || 'The model did not answer. Check the Azure OpenAI key on the VM.')
        : (data?.data?.answer || 'The model returned an empty answer.');
      const usedContextId = failure
        ? undefined
        : (data.data?.context_id || (contextMode === 'layer' ? selectedContextId : undefined));
      const usedContextName = failure
        ? undefined
        : (data.data?.context_envelope?.context_name
          || selectedContext?.name
          || (usedContextId ? shortRecordId(usedContextId) : undefined));

      const result: TestResult = {
        fabricId: selectedFabric,
        llmProvider: selectedLLM,
        query: pendingQuery,
        response: answer,
        confidence: failure ? 0 : (data.data?.confidence || 0.85),
        timestamp: new Date().toISOString(),
        relevantChunks: failure ? 0 : (data.data?.relevant_chunks ?? data.data?.relevant_chunks_found ?? 0),
        packedChunks: failure ? 0 : (data.data?.retrieval?.packed_chunks ?? data.data?.relevant_chunks_found ?? 0),
        processingTime: failure ? '0s' : (data.data?.processing_time || '1.2s'),
        sessionId: failure ? undefined : data.data?.session_id,
        episodeId: failure ? undefined : data.data?.episode_id,
        contextId: usedContextId as string | undefined,
        contextName: usedContextName as string | undefined,
        route: failure ? undefined : data.data?.route,
        decision: failure ? undefined : (data.data?.decision || undefined),
        decisionResolver: failure ? undefined : (data.data?.decision_resolver || undefined),
        feedbackState: null,
      };

      if (!failure && data.data?.session_id) {
        setSessionByFabric((prev) => ({ ...prev, [selectedFabric]: data.data.session_id }));
      }

      setTestResults((prev) => [...prev, result]);
      setTestQuery('');
      setStatusBanner({
        type: failure ? 'error' : 'success',
        message: failure ? String(detail || 'Query failed.') : 'Episode recorded.',
      });
    } catch {
      setTestResults((prev) => [
        ...prev,
        {
          fabricId: selectedFabric,
          llmProvider: selectedLLM,
          query: pendingQuery,
          response: 'Sorry, I encountered an error. Please try again.',
          confidence: 0,
          timestamp: new Date().toISOString(),
          relevantChunks: 0,
          processingTime: '0s',
          contextId: contextMode === 'layer' ? selectedContextId || undefined : undefined,
          contextName: contextMode === 'layer' ? selectedContext?.name : undefined,
          feedbackState: null,
        },
      ]);
      setStatusBanner({ type: 'error', message: 'Query failed. Please try again.' });
    } finally {
      setIsLoading(false);
      composerRef.current?.focus();
    }
  };

  const submitFeedback = async (index: number, rating: 'up' | 'down', applyCorrection: boolean) => {
    const result = testResults[index];
    if (!result?.episodeId || !result?.fabricId) {
      setStatusBanner({ type: 'info', message: 'This answer has no episode id yet. Run the query again after restart.' });
      return;
    }
    const correction = (feedbackDrafts[index] || '').trim();
    try {
      const response = await apiRequest('api/v1/agent/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fabric_id: result.fabricId,
          episode_id: result.episodeId,
          session_id: result.sessionId,
          rating,
          outcome: rating === 'up' ? 'helpful' : 'incorrect',
          correction_text: correction || undefined,
        }),
      });
      const data = await response.json();
      if (!data.success) {
        setStatusBanner({ type: 'error', message: data.error || data.message || 'Feedback failed.' });
        return;
      }
      let note = rating === 'up' ? 'Marked helpful.' : 'Correction queued.';
      const candidateId = data.data?.enrichment_candidate_id;
      if (applyCorrection && candidateId) {
        const approve = await apiRequest(`api/v1/agent/enrichment/${candidateId}/approve`, { method: 'POST' });
        const approved = await approve.json();
        note = approved.success
          ? 'Correction written into the fabric. Later answers will use it.'
          : (approved.error || approved.message || 'Could not apply correction.');
      }
      setTestResults((prev) => prev.map((item, i) => (i === index ? { ...item, feedbackState: note } : item)));
      setStatusBanner({ type: 'success', message: note });
    } catch {
      setStatusBanner({ type: 'error', message: 'Feedback request failed.' });
    }
  };

  const canSend =
    Boolean(selectedFabric)
    && Boolean(testQuery.trim())
    && !isLoading
    && !(contextMode === 'layer' && !selectedContextId);

  return (
    <div
      className="relative -mx-4 -mb-8 min-h-[calc(100vh-4.5rem)] overflow-hidden px-4 pb-4 text-[#e8edf4] sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
      style={{ fontFamily: "Outfit, 'Plus Jakarta Sans', system-ui, sans-serif" }}
    >
      {/* Soft weave atmosphere only — no white plate */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(94,200,242,0.08),_transparent_50%),radial-gradient(ellipse_at_bottom_right,_rgba(62,207,155,0.06),_transparent_45%)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.22]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(148,163,184,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.07) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      <div className="relative mx-auto flex h-[calc(100vh-5.5rem)] max-w-[1400px] flex-col gap-3 pt-3">
        <header className="flex shrink-0 items-center justify-between gap-3 rounded-[22px] border border-[rgba(148,163,184,0.14)] bg-[#101822]/78 px-5 py-3 shadow-[0_18px_50px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-2xl">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#8b9cb0]">Weave · Agent lab</p>
            <h1 className="truncate text-[22px] font-semibold tracking-[-0.03em] text-[#e8edf4]">Test with LLM</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setRailOpen((v) => !v)}
              className="rounded-full border border-[rgba(148,163,184,0.2)] bg-white/[0.04] px-3 py-1.5 text-[11px] font-medium text-[#cbd5e1] transition hover:bg-white/[0.08] lg:hidden"
            >
              {railOpen ? 'Hide setup' : 'Setup'}
            </button>
            {testResults.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  setTestResults([]);
                  setFeedbackDrafts({});
                  setStatusBanner({ type: 'info', message: 'Conversation cleared.' });
                }}
                className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(148,163,184,0.2)] bg-white/[0.04] px-3 py-1.5 text-[11px] font-medium text-[#cbd5e1] transition hover:bg-white/[0.08]"
              >
                <TrashIcon className="h-3.5 w-3.5" />
                Clear
              </button>
            )}
            <span className="hidden rounded-full border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.12)] px-3 py-1.5 text-[11px] font-medium text-[#9adfff] sm:inline">
              {contextMode === 'layer' ? 'Fabric + Context' : 'Fabric only'}
            </span>
          </div>
        </header>

        {statusBanner && (
          <div
            className={`shrink-0 rounded-2xl border px-4 py-2.5 text-[13px] ${
              statusBanner.type === 'success'
                ? 'border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.1)] text-[#9af0ca]'
                : statusBanner.type === 'error'
                  ? 'border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.1)] text-[#f3b4b0]'
                  : 'border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.1)] text-[#9adfff]'
            }`}
          >
            {statusBanner.message}
          </div>
        )}

        <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside
            className={`${railOpen ? 'flex' : 'hidden'} min-h-0 flex-col gap-3 overflow-y-auto rounded-[26px] border border-[rgba(148,163,184,0.14)] bg-[#0c121c]/88 p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.65)] backdrop-blur-2xl lg:flex`}
          >
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b9cb0]">1 · Fabric</p>
              <select
                value={selectedFabric}
                onChange={(e) => {
                  setSelectedFabric(e.target.value);
                  setSelectedContextId('');
                  setContextMode('fabric');
                }}
                disabled={loadingFabrics}
                className="mt-2 w-full appearance-none rounded-2xl border border-[rgba(148,163,184,0.2)] bg-[#10141d]/80 px-3 py-2.5 text-[13px] text-[#e8edf4] outline-none transition focus:border-[rgba(94,200,242,0.45)]"
              >
                <option value="">{loadingFabrics ? 'Loading…' : 'Choose a fabric'}</option>
                {fabrics.map((fabric) => (
                  <option key={fabric.id} value={fabric.id}>
                    {fabric.name} · {fabricKindLabel(fabric.weave_domain)}
                  </option>
                ))}
              </select>
              {activeFabric && (
                <div className="mt-2 rounded-2xl border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-3 py-2">
                  <p className="truncate text-[12px] font-medium text-[#e8edf4]">{activeFabric.name}</p>
                  <p className="mt-0.5 font-mono text-[10px] text-[#8b9cb0]">
                    {fabricKindLabel(activeFabric.weave_domain)} · {activeFabric.document_count} docs
                    {sessionByFabric[selectedFabric] ? ` · sess ${shortRecordId(sessionByFabric[selectedFabric])}` : ''}
                  </p>
                </div>
              )}
            </div>

            <div className="rounded-[22px] border border-[rgba(94,200,242,0.22)] bg-[linear-gradient(160deg,rgba(94,200,242,0.08),rgba(12,18,28,0.9))] p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#5ec8f2]">2 · Context Layer</p>
                  <p className="mt-1 text-[13px] font-medium text-[#e8edf4]">Operating contract</p>
                </div>
                <Link to="/context" className="text-[11px] font-medium text-[#5ec8f2] hover:underline">
                  Design →
                </Link>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-1 rounded-2xl bg-[#070b12]/70 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setContextMode('fabric');
                    setSelectedContextId('');
                  }}
                  className={`rounded-xl px-2.5 py-2 text-left transition ${
                    contextMode === 'fabric'
                      ? 'bg-white/[0.1] text-[#e8edf4] shadow-sm ring-1 ring-[rgba(148,163,184,0.25)]'
                      : 'text-[#8b9cb0] hover:text-[#cbd5e1]'
                  }`}
                >
                  <p className="text-[11px] font-semibold">Fabric only</p>
                  <p className="text-[10px] opacity-70">No contract</p>
                </button>
                <button
                  type="button"
                  disabled={loadingContexts || publishedContexts.length === 0}
                  onClick={() => {
                    setContextMode('layer');
                    if (!selectedContextId && publishedContexts[0]) {
                      setSelectedContextId(publishedContexts[0].id);
                    }
                  }}
                  className={`rounded-xl px-2.5 py-2 text-left transition disabled:opacity-40 ${
                    contextMode === 'layer'
                      ? 'bg-gradient-to-br from-[rgba(94,200,242,0.22)] to-[rgba(62,207,155,0.12)] text-[#e8edf4] ring-1 ring-[rgba(94,200,242,0.35)]'
                      : 'text-[#8b9cb0] hover:text-[#cbd5e1]'
                  }`}
                >
                  <p className="text-[11px] font-semibold">+ Context</p>
                  <p className="text-[10px] opacity-70">
                    {loadingContexts ? '…' : publishedContexts.length ? `${publishedContexts.length} live` : 'None'}
                  </p>
                </button>
              </div>
              {contextMode === 'layer' && (
                <div className="mt-2 max-h-40 space-y-1.5 overflow-y-auto">
                  {publishedContexts.map((ctx) => {
                    const active = selectedContextId === ctx.id;
                    return (
                      <button
                        key={ctx.id}
                        type="button"
                        onClick={() => setSelectedContextId(ctx.id)}
                        className={`w-full rounded-xl border px-2.5 py-2 text-left transition ${
                          active
                            ? 'border-[rgba(62,207,155,0.5)] bg-[rgba(62,207,155,0.12)] text-[#e8edf4]'
                            : 'border-[rgba(148,163,184,0.14)] bg-[#0b0f16]/50 text-[#cbd5e1] hover:border-[rgba(94,200,242,0.35)]'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-[12px] font-medium">{ctx.name}</p>
                          {active ? <CheckCircleIcon className="h-4 w-4 shrink-0 text-[#3ecf9b]" /> : <LinkIcon className="h-3.5 w-3.5 shrink-0 text-[#8b9cb0]" />}
                        </div>
                        <p className="mt-0.5 font-mono text-[10px] text-[#8b9cb0]">
                          v{ctx.version} · {shortRecordId(ctx.id)}
                        </p>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b9cb0]">3 · Model</p>
              <select
                value={selectedLLM}
                onChange={(e) => setSelectedLLM(e.target.value)}
                className="mt-2 w-full appearance-none rounded-2xl border border-[rgba(148,163,184,0.2)] bg-[#10141d]/80 px-3 py-2.5 text-[13px] text-[#e8edf4] outline-none focus:border-[rgba(94,200,242,0.45)]"
              >
                {(llmProviders.length > 0 ? llmProviders : [{ id: 'openai', name: 'Azure OpenAI' }]).map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-auto rounded-[22px] border border-[rgba(148,163,184,0.14)] bg-[#10141d]/55 p-3">
              <div className="flex items-center gap-2">
                <SparklesIcon className="h-4 w-4 text-[#5ec8f2]" />
                <p className="text-[11px] font-semibold text-[#e8edf4]">Prove the layer</p>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-[#8b9cb0]">
                {selectedFabric ? demoAdjudication.hint : 'Select a fabric to load the right demo anchors.'}
              </p>
              <div className="mt-2 grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  disabled={!selectedFabric}
                  onClick={() => {
                    setTestQuery(demoAdjudication.query);
                    setContextMode('fabric');
                    setSelectedContextId('');
                    composerRef.current?.focus();
                  }}
                  className="rounded-xl border border-[rgba(148,163,184,0.16)] bg-white/[0.04] px-2 py-2 text-left text-[10px] font-semibold text-[#e8edf4] disabled:opacity-40"
                >
                  Step 1 · Fabric
                  <span className="mt-0.5 block font-normal text-[#8b9cb0]">{demoAdjudication.label}</span>
                </button>
                <button
                  type="button"
                  disabled={!selectedFabric || !publishedContexts.length}
                  onClick={() => {
                    setTestQuery(demoAdjudication.query);
                    setContextMode('layer');
                    if (publishedContexts[0]) setSelectedContextId(publishedContexts[0].id);
                    composerRef.current?.focus();
                  }}
                  className="rounded-xl bg-gradient-to-r from-[#0ea5e9] to-[#10b981] px-2 py-2 text-left text-[10px] font-semibold text-white disabled:opacity-40"
                >
                  Step 2 · Context
                  <span className="mt-0.5 block font-normal text-white/70">
                    expect {demoAdjudication.expectWithContext}
                  </span>
                </button>
              </div>
            </div>
          </aside>

          <section className="flex min-h-0 flex-col overflow-hidden rounded-[28px] border border-[rgba(148,163,184,0.14)] bg-[#0c121c]/82 shadow-[0_24px_80px_-40px_rgba(0,0,0,0.7)] backdrop-blur-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-[rgba(148,163,184,0.12)] px-5 py-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b9cb0]">Conversation</p>
                <p className="text-[13px] font-medium text-[#e8edf4]">
                  {testResults.length === 0
                    ? 'No episodes yet'
                    : `${testResults.length} episode${testResults.length === 1 ? '' : 's'} · newest at bottom`}
                </p>
              </div>
              <span className="rounded-full border border-[rgba(148,163,184,0.16)] bg-white/[0.04] px-2 py-1 font-mono text-[10px] text-[#8b9cb0]">
                {activeFabric ? shortRecordId(activeFabric.id) : 'no fabric'}
              </span>
            </div>

            <div ref={transcriptRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
              {testResults.length === 0 && !isLoading && (
                <div className="flex h-full min-h-[280px] flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-[22px] border border-[rgba(94,200,242,0.25)] bg-[linear-gradient(160deg,rgba(94,200,242,0.14),rgba(16,20,29,0.7))] shadow-[0_16px_40px_-20px_rgba(94,200,242,0.45)]">
                    <SparklesIcon className="h-7 w-7 text-[#5ec8f2]" />
                  </div>
                  <p className="mt-5 text-[20px] font-semibold tracking-[-0.03em] text-[#e8edf4]">Ask the fabric</p>
                  <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-[#8b9cb0]">
                    Setup stays on the left. Outcomes stream here like a lab notebook — structured sections, locked decisions, no endless page scroll.
                  </p>
                </div>
              )}

              {testResults.map((result, index) => (
                <article key={`${result.timestamp}-${index}`} className="mx-auto w-full max-w-3xl space-y-3">
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-[22px] rounded-br-md bg-gradient-to-br from-[#0ea5e9] to-[#0891b2] px-4 py-3 text-[14px] leading-relaxed text-white shadow-[0_12px_32px_-16px_rgba(14,165,233,0.75)]">
                      {result.query}
                    </div>
                  </div>

                  <div className="rounded-[24px] border border-[rgba(148,163,184,0.14)] bg-[#10141d]/75 p-4 shadow-[0_16px_40px_-28px_rgba(0,0,0,0.55)] sm:p-5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="rounded-full border border-[rgba(148,163,184,0.16)] bg-white/[0.04] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#cbd5e1]">
                        {result.contextId ? 'Fabric + Context' : 'Fabric only'}
                      </span>
                      {result.contextName && (
                        <span className="rounded-full border border-[rgba(94,200,242,0.3)] bg-[rgba(94,200,242,0.1)] px-2 py-0.5 text-[10px] font-medium text-[#9adfff]">
                          {result.contextName}
                        </span>
                      )}
                      {result.decision && (
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${decisionTone(result.decision)}`}>
                          Decision · {result.decision}
                        </span>
                      )}
                      {result.decisionResolver === 'deterministic' && (
                        <span className="rounded-full border border-[rgba(251,191,36,0.35)] bg-[rgba(251,191,36,0.1)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#fcd34d]">
                          Locked
                        </span>
                      )}
                      {result.route && !result.decision && (
                        <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium text-[#8b9cb0]">
                          {result.route}
                        </span>
                      )}
                      <span className="ml-auto text-[10px] text-[#8b9cb0]">
                        {new Date(result.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    <div className="mt-4">
                      <ScientificAnswer markdown={result.response} decision={result.decision} />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2 border-t border-[rgba(148,163,184,0.12)] pt-3 text-[10px] text-[#8b9cb0]">
                      <span className="rounded-lg border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-2 py-1">
                        Confidence {(result.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="rounded-lg border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-2 py-1">{result.processingTime}</span>
                      <span className="rounded-lg border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-2 py-1">
                        Chunks {result.relevantChunks}
                        {result.packedChunks && result.packedChunks !== result.relevantChunks
                          ? ` · packed ${result.packedChunks}`
                          : ''}
                      </span>
                      {result.sessionId && (
                        <span className="rounded-lg border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-2 py-1 font-mono" title={result.sessionId}>
                          sess {shortRecordId(result.sessionId)}
                        </span>
                      )}
                      {result.episodeId && (
                        <span className="rounded-lg border border-[rgba(148,163,184,0.12)] bg-white/[0.03] px-2 py-1 font-mono" title={result.episodeId}>
                          ep {shortRecordId(result.episodeId)}
                        </span>
                      )}
                    </div>

                    {result.episodeId && (
                      <div className="mt-3 space-y-2 rounded-2xl border border-[rgba(148,163,184,0.12)] bg-[#0b0f16]/55 p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8b9cb0]">
                          Closed loop
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => submitFeedback(index, 'up', false)}
                            className="rounded-full border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.1)] px-3 py-1 text-[11px] font-medium text-[#9af0ca]"
                          >
                            Helpful
                          </button>
                          <button
                            type="button"
                            onClick={() => submitFeedback(index, 'down', false)}
                            className="rounded-full border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.1)] px-3 py-1 text-[11px] font-medium text-[#f3b4b0]"
                          >
                            Incorrect
                          </button>
                        </div>
                        <textarea
                          value={feedbackDrafts[index] || ''}
                          onChange={(e) => setFeedbackDrafts((prev) => ({ ...prev, [index]: e.target.value }))}
                          placeholder="Correction to write back into this fabric"
                          rows={2}
                          className="w-full rounded-xl border border-[rgba(148,163,184,0.2)] bg-[#10141d]/80 px-3 py-2 text-[12px] text-[#e8edf4] outline-none placeholder:text-[#8b9cb0] focus:border-[rgba(94,200,242,0.4)]"
                        />
                        <button
                          type="button"
                          onClick={() => submitFeedback(index, 'down', true)}
                          className="rounded-full bg-emerald-600 px-3 py-1.5 text-[11px] font-medium text-white"
                        >
                          Apply correction to fabric
                        </button>
                        {result.feedbackState && (
                          <p className="text-[11px] text-[#9af0ca]">{result.feedbackState}</p>
                        )}
                      </div>
                    )}
                  </div>
                </article>
              ))}

              {isLoading && (
                <div className="mx-auto flex w-full max-w-3xl items-center gap-3 rounded-[22px] border border-[rgba(148,163,184,0.16)] bg-[#10141d]/80 px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#5ec8f2]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#5ec8f2] [animation-delay:120ms]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#5ec8f2] [animation-delay:240ms]" />
                  </div>
                  <p className="text-[12px] text-[#8b9cb0]">
                    {contextMode === 'layer' ? 'Adjudicating with Context Layer…' : 'Retrieving from fabric…'}
                  </p>
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-[rgba(148,163,184,0.12)] bg-[#0b0f16]/70 p-3 backdrop-blur-xl sm:p-4">
              <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-[26px] border border-[rgba(148,163,184,0.2)] bg-[#10141d]/85 p-2 shadow-[0_12px_40px_-24px_rgba(0,0,0,0.7)] focus-within:border-[rgba(94,200,242,0.4)]">
                <textarea
                  ref={composerRef}
                  value={testQuery}
                  onChange={(e) => setTestQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      if (canSend) void handleTestQuery();
                    }
                  }}
                  rows={2}
                  placeholder={
                    selectedFabric
                      ? contextMode === 'layer'
                        ? 'Ask under the attached Context Layer…'
                        : 'Ask the fabric…'
                      : 'Select a fabric to begin'
                  }
                  className="max-h-36 min-h-[52px] flex-1 resize-none bg-transparent px-3 py-2.5 text-[14px] leading-relaxed text-[#e8edf4] outline-none placeholder:text-[#8b9cb0]"
                />
                <button
                  type="button"
                  disabled={!canSend}
                  onClick={() => void handleTestQuery()}
                  className="mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#0ea5e9] to-[#10b981] text-white shadow-[0_8px_24px_-10px_rgba(94,200,242,0.85)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:from-[#334155] disabled:to-[#334155] disabled:shadow-none"
                  aria-label="Send"
                >
                  <ArrowUpIcon className="h-5 w-5" />
                </button>
              </div>
              <p className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-[#8b9cb0]">
                Enter to send · Shift+Enter for newline · Outcomes stay in this panel
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TestLLM;
