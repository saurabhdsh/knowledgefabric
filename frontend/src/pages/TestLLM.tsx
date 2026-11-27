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
  if (d === 'pay') return 'bg-[#e8f8ef] text-[#1b7a45] border-[#b7ebc9]';
  if (d === 'deny') return 'bg-[#fdecee] text-[#b42318] border-[#f3c0c0]';
  if (d === 'hold') return 'bg-[#fff6e5] text-[#b54708] border-[#f7d7a8]';
  if (d === 'human_review') return 'bg-[#eef2ff] text-[#3538cd] border-[#c7d2fe]';
  return 'bg-[#f3f4f6] text-[#52525b] border-[#e4e4e7]';
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
                ? 'border-[#d7dde7] bg-gradient-to-b from-white to-[#f7f8fa] shadow-[0_1px_0_rgba(255,255,255,0.8)_inset]'
                : 'border-[#eceef2] bg-white/80'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b93a7]">
                {section.title}
              </p>
              {isDecision && decision && (
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${decisionTone(decision)}`}>
                  {decision}
                </span>
              )}
            </div>
            <div className="mt-2 text-[14px] leading-[1.65] text-[#1d1d1f] [&_strong]:text-[#111]">
              {renderLlmMarkdown(section.body, 'light')}
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
      className="relative -mx-4 -mb-8 min-h-[calc(100vh-4.5rem)] overflow-hidden px-4 pb-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
      style={{ fontFamily: "Outfit, 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif" }}
    >
      {/* Atmosphere */}
      <div className="pointer-events-none absolute inset-0 bg-[#f5f5f7]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(255,255,255,0.95),_transparent_55%),radial-gradient(ellipse_at_bottom_right,_rgba(210,220,235,0.55),_transparent_45%)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(15,23,42,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,0.03) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      <div className="relative mx-auto flex h-[calc(100vh-5.5rem)] max-w-[1400px] flex-col gap-3 pt-3">
        {/* Top bar */}
        <header className="flex shrink-0 items-center justify-between gap-3 rounded-[22px] border border-white/70 bg-white/70 px-5 py-3 shadow-[0_10px_40px_-28px_rgba(15,23,42,0.35)] backdrop-blur-2xl">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#8b93a7]">Weave · Agent lab</p>
            <h1 className="truncate text-[22px] font-semibold tracking-[-0.03em] text-[#1d1d1f]">Test with LLM</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setRailOpen((v) => !v)}
              className="rounded-full border border-[#e5e7eb] bg-white px-3 py-1.5 text-[11px] font-medium text-[#52525b] transition hover:bg-[#f9fafb] lg:hidden"
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
                className="inline-flex items-center gap-1.5 rounded-full border border-[#e5e7eb] bg-white px-3 py-1.5 text-[11px] font-medium text-[#52525b] transition hover:bg-[#f9fafb]"
              >
                <TrashIcon className="h-3.5 w-3.5" />
                Clear
              </button>
            )}
            <span className="hidden rounded-full bg-[#1d1d1f] px-3 py-1.5 text-[11px] font-medium text-white sm:inline">
              {contextMode === 'layer' ? 'Fabric + Context' : 'Fabric only'}
            </span>
          </div>
        </header>

        {statusBanner && (
          <div
            className={`shrink-0 rounded-2xl border px-4 py-2.5 text-[13px] ${
              statusBanner.type === 'success'
                ? 'border-[#b7ebc9] bg-[#e8f8ef] text-[#1b7a45]'
                : statusBanner.type === 'error'
                  ? 'border-[#f3c0c0] bg-[#fdecee] text-[#b42318]'
                  : 'border-[#c7d2fe] bg-[#eef2ff] text-[#3538cd]'
            }`}
          >
            {statusBanner.message}
          </div>
        )}

        <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
          {/* Setup rail */}
          <aside
            className={`${railOpen ? 'flex' : 'hidden'} min-h-0 flex-col gap-3 overflow-y-auto rounded-[26px] border border-white/80 bg-white/75 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)] backdrop-blur-2xl lg:flex`}
          >
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b93a7]">1 · Fabric</p>
              <select
                value={selectedFabric}
                onChange={(e) => {
                  setSelectedFabric(e.target.value);
                  setSelectedContextId('');
                  setContextMode('fabric');
                }}
                disabled={loadingFabrics}
                className="mt-2 w-full appearance-none rounded-2xl border border-[#e8eaef] bg-[#f7f8fa] px-3 py-2.5 text-[13px] text-[#1d1d1f] outline-none transition focus:border-[#c5ccd8] focus:bg-white"
              >
                <option value="">{loadingFabrics ? 'Loading…' : 'Choose a fabric'}</option>
                {fabrics.map((fabric) => (
                  <option key={fabric.id} value={fabric.id}>
                    {fabric.name} · {fabricKindLabel(fabric.weave_domain)}
                  </option>
                ))}
              </select>
              {activeFabric && (
                <div className="mt-2 rounded-2xl bg-[#f7f8fa] px-3 py-2">
                  <p className="truncate text-[12px] font-medium text-[#1d1d1f]">{activeFabric.name}</p>
                  <p className="mt-0.5 font-mono text-[10px] text-[#8b93a7]">
                    {fabricKindLabel(activeFabric.weave_domain)} · {activeFabric.document_count} docs
                    {sessionByFabric[selectedFabric] ? ` · sess ${shortRecordId(sessionByFabric[selectedFabric])}` : ''}
                  </p>
                </div>
              )}
            </div>

            <div className="rounded-[22px] border border-[#eceef2] bg-gradient-to-b from-white to-[#f7f8fa] p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b93a7]">2 · Context Layer</p>
                  <p className="mt-1 text-[13px] font-medium text-[#1d1d1f]">Operating contract</p>
                </div>
                <Link to="/context" className="text-[11px] font-medium text-[#0071e3] hover:underline">
                  Design →
                </Link>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-1 rounded-2xl bg-[#eceef2]/80 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setContextMode('fabric');
                    setSelectedContextId('');
                  }}
                  className={`rounded-xl px-2.5 py-2 text-left transition ${
                    contextMode === 'fabric' ? 'bg-white text-[#1d1d1f] shadow-sm' : 'text-[#6b7280]'
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
                    contextMode === 'layer' ? 'bg-white text-[#1d1d1f] shadow-sm' : 'text-[#6b7280]'
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
                            ? 'border-[#1d1d1f] bg-[#1d1d1f] text-white'
                            : 'border-[#e8eaef] bg-white text-[#1d1d1f] hover:border-[#c5ccd8]'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-[12px] font-medium">{ctx.name}</p>
                          {active ? <CheckCircleIcon className="h-4 w-4 shrink-0" /> : <LinkIcon className="h-3.5 w-3.5 shrink-0 opacity-40" />}
                        </div>
                        <p className={`mt-0.5 font-mono text-[10px] ${active ? 'text-white/60' : 'text-[#8b93a7]'}`}>
                          v{ctx.version} · {shortRecordId(ctx.id)}
                        </p>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b93a7]">3 · Model</p>
              <select
                value={selectedLLM}
                onChange={(e) => setSelectedLLM(e.target.value)}
                className="mt-2 w-full appearance-none rounded-2xl border border-[#e8eaef] bg-[#f7f8fa] px-3 py-2.5 text-[13px] text-[#1d1d1f] outline-none focus:border-[#c5ccd8] focus:bg-white"
              >
                {(llmProviders.length > 0 ? llmProviders : [{ id: 'openai', name: 'Azure OpenAI' }]).map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-auto rounded-[22px] border border-[#eceef2] bg-[#f7f8fa] p-3">
              <div className="flex items-center gap-2">
                <SparklesIcon className="h-4 w-4 text-[#0071e3]" />
                <p className="text-[11px] font-semibold text-[#1d1d1f]">Prove the layer</p>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-[#6b7280]">
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
                  className="rounded-xl bg-white px-2 py-2 text-left text-[10px] font-semibold text-[#1d1d1f] shadow-sm disabled:opacity-40"
                >
                  Step 1 · Fabric
                  <span className="mt-0.5 block font-normal text-[#8b93a7]">{demoAdjudication.label}</span>
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
                  className="rounded-xl bg-[#1d1d1f] px-2 py-2 text-left text-[10px] font-semibold text-white disabled:opacity-40"
                >
                  Step 2 · Context
                  <span className="mt-0.5 block font-normal text-white/55">
                    expect {demoAdjudication.expectWithContext}
                  </span>
                </button>
              </div>
            </div>
          </aside>

          {/* Chat stage */}
          <section className="flex min-h-0 flex-col overflow-hidden rounded-[28px] border border-white/80 bg-white/65 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.55)] backdrop-blur-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-[#eceef2]/90 px-5 py-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8b93a7]">Conversation</p>
                <p className="text-[13px] font-medium text-[#1d1d1f]">
                  {testResults.length === 0
                    ? 'No episodes yet'
                    : `${testResults.length} episode${testResults.length === 1 ? '' : 's'} · newest at bottom`}
                </p>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-[#8b93a7]">
                <span className="rounded-full bg-[#f3f4f6] px-2 py-1 font-mono">
                  {activeFabric ? shortRecordId(activeFabric.id) : 'no fabric'}
                </span>
              </div>
            </div>

            <div ref={transcriptRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
              {testResults.length === 0 && !isLoading && (
                <div className="flex h-full min-h-[280px] flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-[22px] bg-gradient-to-b from-white to-[#eef1f6] shadow-[0_12px_40px_-20px_rgba(15,23,42,0.35)]">
                    <SparklesIcon className="h-7 w-7 text-[#1d1d1f]" />
                  </div>
                  <p className="mt-5 text-[20px] font-semibold tracking-[-0.03em] text-[#1d1d1f]">Ask the fabric</p>
                  <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-[#6b7280]">
                    Setup stays on the left. Outcomes stream here like a lab notebook — structured sections, locked decisions, no endless page scroll.
                  </p>
                </div>
              )}

              {testResults.map((result, index) => (
                <article key={`${result.timestamp}-${index}`} className="mx-auto w-full max-w-3xl space-y-3">
                  {/* User bubble */}
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-[22px] rounded-br-md bg-[#0071e3] px-4 py-3 text-[14px] leading-relaxed text-white shadow-[0_10px_30px_-18px_rgba(0,113,227,0.8)]">
                      {result.query}
                    </div>
                  </div>

                  {/* Assistant scientific card */}
                  <div className="rounded-[24px] border border-[#e8eaef] bg-white p-4 shadow-[0_16px_40px_-32px_rgba(15,23,42,0.4)] sm:p-5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="rounded-full bg-[#f3f4f6] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#52525b]">
                        {result.contextId ? 'Fabric + Context' : 'Fabric only'}
                      </span>
                      {result.contextName && (
                        <span className="rounded-full border border-[#dbeafe] bg-[#eff6ff] px-2 py-0.5 text-[10px] font-medium text-[#1d4ed8]">
                          {result.contextName}
                        </span>
                      )}
                      {result.decision && (
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${decisionTone(result.decision)}`}>
                          Decision · {result.decision}
                        </span>
                      )}
                      {result.decisionResolver === 'deterministic' && (
                        <span className="rounded-full border border-[#fde68a] bg-[#fffbeb] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#b45309]">
                          Locked
                        </span>
                      )}
                      {result.route && !result.decision && (
                        <span className="rounded-full bg-[#f3f4f6] px-2 py-0.5 text-[10px] font-medium text-[#6b7280]">
                          {result.route}
                        </span>
                      )}
                      <span className="ml-auto text-[10px] text-[#8b93a7]">
                        {new Date(result.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    <div className="mt-4">
                      <ScientificAnswer markdown={result.response} decision={result.decision} />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2 border-t border-[#f0f1f4] pt-3 text-[10px] text-[#8b93a7]">
                      <span className="rounded-lg bg-[#f7f8fa] px-2 py-1">
                        Confidence {(result.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="rounded-lg bg-[#f7f8fa] px-2 py-1">{result.processingTime}</span>
                      <span className="rounded-lg bg-[#f7f8fa] px-2 py-1">
                        Chunks {result.relevantChunks}
                        {result.packedChunks && result.packedChunks !== result.relevantChunks
                          ? ` · packed ${result.packedChunks}`
                          : ''}
                      </span>
                      {result.sessionId && (
                        <span className="rounded-lg bg-[#f7f8fa] px-2 py-1 font-mono" title={result.sessionId}>
                          sess {shortRecordId(result.sessionId)}
                        </span>
                      )}
                      {result.episodeId && (
                        <span className="rounded-lg bg-[#f7f8fa] px-2 py-1 font-mono" title={result.episodeId}>
                          ep {shortRecordId(result.episodeId)}
                        </span>
                      )}
                    </div>

                    {result.episodeId && (
                      <div className="mt-3 space-y-2 rounded-2xl bg-[#f7f8fa] p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8b93a7]">
                          Closed loop
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => submitFeedback(index, 'up', false)}
                            className="rounded-full bg-white px-3 py-1 text-[11px] font-medium text-[#1b7a45] shadow-sm"
                          >
                            Helpful
                          </button>
                          <button
                            type="button"
                            onClick={() => submitFeedback(index, 'down', false)}
                            className="rounded-full bg-white px-3 py-1 text-[11px] font-medium text-[#b42318] shadow-sm"
                          >
                            Incorrect
                          </button>
                        </div>
                        <textarea
                          value={feedbackDrafts[index] || ''}
                          onChange={(e) => setFeedbackDrafts((prev) => ({ ...prev, [index]: e.target.value }))}
                          placeholder="Correction to write back into this fabric"
                          rows={2}
                          className="w-full rounded-xl border border-[#e8eaef] bg-white px-3 py-2 text-[12px] text-[#1d1d1f] outline-none focus:border-[#c5ccd8]"
                        />
                        <button
                          type="button"
                          onClick={() => submitFeedback(index, 'down', true)}
                          className="rounded-full bg-[#1d1d1f] px-3 py-1.5 text-[11px] font-medium text-white"
                        >
                          Apply correction to fabric
                        </button>
                        {result.feedbackState && (
                          <p className="text-[11px] text-[#1b7a45]">{result.feedbackState}</p>
                        )}
                      </div>
                    )}
                  </div>
                </article>
              ))}

              {isLoading && (
                <div className="mx-auto flex w-full max-w-3xl items-center gap-3 rounded-[22px] border border-[#e8eaef] bg-white/90 px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1d1d1f]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1d1d1f] [animation-delay:120ms]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1d1d1f] [animation-delay:240ms]" />
                  </div>
                  <p className="text-[12px] text-[#6b7280]">
                    {contextMode === 'layer' ? 'Adjudicating with Context Layer…' : 'Retrieving from fabric…'}
                  </p>
                </div>
              )}
            </div>

            {/* Composer */}
            <div className="shrink-0 border-t border-[#eceef2]/90 bg-white/80 p-3 backdrop-blur-xl sm:p-4">
              <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-[26px] border border-[#e5e7eb] bg-[#f7f8fa] p-2 shadow-[0_12px_40px_-28px_rgba(15,23,42,0.35)] focus-within:border-[#c5ccd8] focus-within:bg-white">
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
                  className="max-h-36 min-h-[52px] flex-1 resize-none bg-transparent px-3 py-2.5 text-[14px] leading-relaxed text-[#1d1d1f] outline-none placeholder:text-[#9ca3af]"
                />
                <button
                  type="button"
                  disabled={!canSend}
                  onClick={() => void handleTestQuery()}
                  className="mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#0071e3] text-white shadow-[0_8px_24px_-10px_rgba(0,113,227,0.9)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:bg-[#d1d5db] disabled:shadow-none"
                  aria-label="Send"
                >
                  <ArrowUpIcon className="h-5 w-5" />
                </button>
              </div>
              <p className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-[#8b93a7]">
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
