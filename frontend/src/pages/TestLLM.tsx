import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  DocumentTextIcon,
  CpuChipIcon,
  LinkIcon,
  CheckCircleIcon,
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

function shortRecordId(value?: string): string {
  const id = String(value || '').trim();
  if (!id) return '';
  if (id.length <= 18) return id;
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

const TestLLM: React.FC = () => {
  const [selectedFabric, setSelectedFabric] = useState<string>('');
  const [selectedLLM, setSelectedLLM] = useState<string>('openai');
  const [llmProviders, setLlmProviders] = useState<Array<{ id: string; name: string; description?: string }>>([]);
  const [testQuery, setTestQuery] = useState<string>('');
  const [testResults, setTestResults] = useState<any[]>([]);
  const [sessionByFabric, setSessionByFabric] = useState<Record<string, string>>({});
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<number, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [loadingFabrics, setLoadingFabrics] = useState(true);
  const [statusBanner, setStatusBanner] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);
  const [contextProfiles, setContextProfiles] = useState<PublishedContext[]>([]);
  const [loadingContexts, setLoadingContexts] = useState(false);
  const [selectedContextId, setSelectedContextId] = useState<string>(''); // '' = fabric only
  const [contextMode, setContextMode] = useState<'fabric' | 'layer'>('fabric');

  const selectedContext = useMemo(
    () => contextProfiles.find((p) => p.id === selectedContextId) || null,
    [contextProfiles, selectedContextId]
  );

  const publishedContexts = useMemo(
    () => contextProfiles.filter((p) => p.status === 'published'),
    [contextProfiles]
  );

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
      // Keep selection if still valid; otherwise clear
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

  // Fetch available fabrics on component mount
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
          console.error('Failed to fetch fabrics:', data.message);
          setStatusBanner({
            type: 'error',
            message: data.message || 'Unable to load knowledge fabrics.',
          });
        }
      } catch (error) {
        console.error('Error fetching fabrics:', error);
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
      } catch (error) {
        console.error('Error fetching LLM providers:', error);
      }
    };
    fetchProviders();
  }, []);

  useEffect(() => {
    loadContextsForFabric(selectedFabric);
  }, [selectedFabric, loadContextsForFabric]);

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

    setIsLoading(true);
    setStatusBanner(null);
    
    try {
      const payload: Record<string, unknown> = {
        query: testQuery,
        llm_provider: selectedLLM,
        top_k: 8,
        session_id: sessionByFabric[selectedFabric] || undefined,
      };
      if (contextMode === 'layer' && selectedContextId) {
        payload.context_id = selectedContextId;
      }

      const response = await apiRequest(`api/v1/knowledge/query/${selectedFabric}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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
      const usedContextId = failure ? undefined : (data.data?.context_id || (contextMode === 'layer' ? selectedContextId : undefined));
      const usedContextName = failure
        ? undefined
        : (data.data?.context_envelope?.context_name
          || selectedContext?.name
          || (usedContextId ? shortRecordId(usedContextId) : undefined));
      
      const result = {
        fabricId: selectedFabric,
        llmProvider: selectedLLM,
        query: testQuery,
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
        feedbackState: null as string | null,
      };

      if (!failure && data.data?.session_id) {
        setSessionByFabric((prev) => ({ ...prev, [selectedFabric]: data.data.session_id }));
      }

      setTestResults(prev => [result, ...prev]);
      setStatusBanner({
        type: failure ? 'error' : 'success',
        message: failure ? String(detail || 'Query failed.') : 'Query completed successfully.',
      });
    } catch (error) {
      const errorResult = {
        fabricId: selectedFabric,
        llmProvider: selectedLLM,
        query: testQuery,
        response: 'Sorry, I encountered an error. Please try again.',
        confidence: 0.0,
        timestamp: new Date().toISOString(),
        relevantChunks: 0,
        processingTime: '0s',
        contextId: contextMode === 'layer' ? selectedContextId || undefined : undefined,
        contextName: contextMode === 'layer' ? selectedContext?.name : undefined,
      };
      setTestResults(prev => [errorResult, ...prev]);
      setStatusBanner({
        type: 'error',
        message: 'Query failed. Please try again.',
      });
    } finally {
      setIsLoading(false);
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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.text-gray-300]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_textarea]:bg-[#10141d]/70 [&_textarea]:text-[#e8edf4] [&_textarea]:border-[rgba(148,163,184,0.2)] [&_textarea]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-12 h-12 bg-gradient-to-r from-emerald-500 to-emerald-600 rounded-xl flex items-center justify-center">
            <ChatBubbleLeftRightIcon className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Test with LLM</h1>
            <p className="text-gray-600">
              Ask a fabric alone — or attach a published Context Layer so the agent honors your rules and playbook.
            </p>
          </div>
        </div>
      </div>
      {statusBanner && (
        <div
          className={`mb-6 rounded-xl border px-4 py-3 text-sm ${
            statusBanner.type === 'success'
              ? 'border-emerald-400/35 bg-emerald-500/10 text-emerald-200'
              : statusBanner.type === 'error'
                ? 'border-rose-400/35 bg-rose-500/10 text-rose-200'
                : 'border-cyan-400/35 bg-cyan-500/10 text-cyan-100'
          }`}
        >
          {statusBanner.message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Test Configuration */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
            <SparklesIcon className="w-5 h-5 mr-2 text-emerald-500" />
            Test Configuration
          </h2>
          
                      <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Knowledge Fabric
                </label>
                <select
                  value={selectedFabric}
                  onChange={(e) => {
                    setSelectedFabric(e.target.value);
                    setSelectedContextId('');
                    setContextMode('fabric');
                  }}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  disabled={loadingFabrics}
                >
                  <option value="">
                    {loadingFabrics ? 'Loading fabrics...' : 'Choose a fabric...'}
                  </option>
                  {fabrics.map((fabric) => (
                    <option key={fabric.id} value={fabric.id}>
                      {fabric.name} · {fabricKindLabel(fabric.weave_domain)} ({fabric.document_count} docs)
                    </option>
                  ))}
                </select>
                {selectedFabric && (
                  <div className="mt-3 rounded-xl border border-[rgba(148,163,184,0.14)] bg-white/[0.03] px-3 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">Selected fabric</p>
                        <p className="mt-1 text-sm font-medium leading-snug text-[#e8edf4]">
                          {fabrics.find(f => f.id === selectedFabric)?.name}
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full border border-[rgba(155,139,212,0.4)] bg-gradient-to-r from-[rgba(94,200,242,0.12)] to-[rgba(155,139,212,0.18)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#d7cff5]">
                        CKF ready
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-[#8b9cb0]">
                      <span className="text-[#cbd5e1]">
                        {fabricKindLabel(fabrics.find(f => f.id === selectedFabric)?.weave_domain)}
                      </span>
                      {' · '}domain-aware reasoning is applied automatically for complex questions.
                    </p>
                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div className="rounded-lg border border-[rgba(148,163,184,0.11)] bg-[#10141d]/55 px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">CKF session</p>
                        <p
                          className="mt-1 truncate font-mono text-[11px] text-[#5ec8f2]"
                          title={sessionByFabric[selectedFabric] || 'Starts on the first query'}
                        >
                          {sessionByFabric[selectedFabric]
                            ? shortRecordId(sessionByFabric[selectedFabric])
                            : 'Starts on first query'}
                        </p>
                      </div>
                      <div className="rounded-lg border border-[rgba(148,163,184,0.11)] bg-[#10141d]/55 px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">CKF closed loop</p>
                        <p className="mt-1 text-[11px] text-[#cbd5e1]">Approved corrections rewrite this fabric</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {selectedFabric && (
                <div className="rounded-2xl border border-[rgba(94,200,242,0.28)] bg-[linear-gradient(145deg,rgba(94,200,242,0.1),rgba(16,20,29,0.55))] p-4 shadow-[0_16px_40px_-28px_rgba(94,200,242,0.55)]">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#5ec8f2]">Context Layer</p>
                      <p className="mt-1 text-sm font-semibold text-[#e8edf4]">Attach a published contract</p>
                      <p className="mt-1 text-xs text-[#8b9cb0]">
                        Fabric alone vs fabric + governed rules — same question, different legitimacy.
                      </p>
                    </div>
                    <Link
                      to="/context"
                      className="text-[11px] font-medium text-[#5ec8f2] hover:underline"
                    >
                      Open Context Layer →
                    </Link>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-[#070b12]/55 p-1">
                    <button
                      type="button"
                      onClick={() => {
                        setContextMode('fabric');
                        setSelectedContextId('');
                      }}
                      className={`rounded-lg px-3 py-2.5 text-left transition ${
                        contextMode === 'fabric'
                          ? 'bg-white/[0.1] text-[#e8edf4] shadow-sm ring-1 ring-[rgba(148,163,184,0.25)]'
                          : 'text-[#8b9cb0] hover:text-[#cbd5e1]'
                      }`}
                    >
                      <p className="text-[11px] font-semibold">Fabric only</p>
                      <p className="mt-0.5 text-[10px] opacity-80">No designed contract</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setContextMode('layer');
                        if (!selectedContextId && publishedContexts[0]) {
                          setSelectedContextId(publishedContexts[0].id);
                        }
                      }}
                      disabled={loadingContexts || publishedContexts.length === 0}
                      className={`rounded-lg px-3 py-2.5 text-left transition disabled:opacity-40 ${
                        contextMode === 'layer'
                          ? 'bg-gradient-to-br from-[rgba(94,200,242,0.22)] to-[rgba(62,207,155,0.14)] text-[#e8edf4] shadow-sm ring-1 ring-[rgba(94,200,242,0.4)]'
                          : 'text-[#8b9cb0] hover:text-[#cbd5e1]'
                      }`}
                    >
                      <p className="text-[11px] font-semibold">With Context Layer</p>
                      <p className="mt-0.5 text-[10px] opacity-80">
                        {loadingContexts
                          ? 'Loading…'
                          : publishedContexts.length
                            ? `${publishedContexts.length} published`
                            : 'None published'}
                      </p>
                    </button>
                  </div>

                  {contextMode === 'layer' && (
                    <div className="mt-3 space-y-2">
                      {publishedContexts.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-[rgba(148,163,184,0.25)] px-3 py-3 text-xs text-[#8b9cb0]">
                          No published contexts on this fabric yet. Create one in Context Layer, publish it, then refresh.
                        </p>
                      ) : (
                        publishedContexts.map((ctx) => {
                          const active = selectedContextId === ctx.id;
                          return (
                            <button
                              key={ctx.id}
                              type="button"
                              onClick={() => setSelectedContextId(ctx.id)}
                              className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${
                                active
                                  ? 'border-[rgba(62,207,155,0.5)] bg-[rgba(62,207,155,0.1)]'
                                  : 'border-[rgba(148,163,184,0.16)] bg-[#0b0f16]/50 hover:border-[rgba(94,200,242,0.35)]'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-medium text-[#e8edf4]">{ctx.name}</p>
                                  <p className="mt-0.5 font-mono text-[10px] text-[#8b9cb0]">
                                    v{ctx.version} · {shortRecordId(ctx.id)}
                                  </p>
                                  {ctx.purpose && (
                                    <p className="mt-1 line-clamp-2 text-[11px] text-[#9fb0c5]">{ctx.purpose}</p>
                                  )}
                                  {(ctx.playbook?.routes || []).length > 0 && (
                                    <p className="mt-1 text-[10px] text-[#7ad4c0]">
                                      Playbook: {(ctx.playbook?.routes || []).join(' · ')}
                                    </p>
                                  )}
                                </div>
                                {active ? (
                                  <CheckCircleIcon className="h-5 w-5 shrink-0 text-[#3ecf9b]" />
                                ) : (
                                  <LinkIcon className="h-4 w-4 shrink-0 text-[#8b9cb0]" />
                                )}
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  )}

                  <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">
                    <span className={`rounded-full px-2 py-0.5 ${contextMode === 'fabric' ? 'bg-white/10 text-[#cbd5e1]' : 'bg-[rgba(62,207,155,0.15)] text-[#9af0ca]'}`}>
                      {contextMode === 'fabric' ? 'Mode · fabric only' : 'Mode · fabric + context'}
                    </span>
                    {contextMode === 'layer' && selectedContext && (
                      <span className="truncate rounded-full bg-[rgba(94,200,242,0.12)] px-2 py-0.5 text-[#9adfff] normal-case tracking-normal">
                        Attached: {selectedContext.name}
                      </span>
                    )}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select LLM Provider
                </label>
                <select
                  value={selectedLLM}
                  onChange={(e) => setSelectedLLM(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {(llmProviders.length > 0 ? llmProviders : [{ id: 'openai', name: 'Azure OpenAI' }]).map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  {llmProviders.find((p) => p.id === selectedLLM)?.description
                    || (selectedLLM === 'bedrock'
                      ? 'Using AWS Bedrock via IAM (no OpenAI key required on AWS)'
                      : 'Questions are answered by the Azure OpenAI deployment on this VM.')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Test Query
                </label>
                <textarea
                  value={testQuery}
                  onChange={(e) => setTestQuery(e.target.value)}
                  placeholder="Enter your test query here..."
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                />
              </div>

            <button
              onClick={handleTestQuery}
              disabled={
                !selectedFabric
                || !testQuery.trim()
                || isLoading
                || (contextMode === 'layer' && !selectedContextId)
              }
              className={`w-full px-6 py-3 rounded-lg font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center ${
                contextMode === 'layer'
                  ? 'bg-gradient-to-r from-cyan-500 to-emerald-500 hover:from-cyan-600 hover:to-emerald-600 shadow-[0_12px_28px_-16px_rgba(94,200,242,0.8)]'
                  : 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700'
              }`}
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  Testing...
                </>
              ) : (
                <>
                  <CpuChipIcon className="w-5 h-5 mr-2" />
                  {contextMode === 'layer' ? 'Run with Context Layer' : 'Run · Fabric only'}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Test Results */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
            <DocumentTextIcon className="w-5 h-5 mr-2 text-emerald-500" />
            Test Results
          </h2>
          
          <div className="space-y-4">
            {testResults.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <ChatBubbleLeftRightIcon className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>No test results yet.</p>
                <p className="mt-1 text-sm text-gray-400">
                  Run once on Fabric only, then again with a Context Layer — compare badges side by side.
                </p>
              </div>
            ) : (
              testResults.map((result, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-gray-900">
                          {fabrics.find(f => f.id === result.fabricId)?.name || 'Unknown Fabric'}
                        </span>
                        <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-gray-600">
                          {result.llmProvider || 'LLM'}
                        </span>
                        {result.contextId ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-cyan-800"
                            title={result.contextId}
                          >
                            <LinkIcon className="h-3 w-3" />
                            Context · {result.contextName || shortRecordId(result.contextId)}
                          </span>
                        ) : (
                          <span className="rounded-full border border-gray-200 bg-white px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">
                            Fabric only
                          </span>
                        )}
                        {(result.decision || result.route) && (
                          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-emerald-800">
                            {result.decision
                              ? `Decision · ${result.decision}`
                              : `Route · ${result.route}`}
                          </span>
                        )}
                        {result.decisionResolver === 'deterministic' && (
                          <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.1em] text-amber-800">
                            Locked
                          </span>
                        )}
                      </div>
                      {(result.sessionId || result.episodeId || result.contextId) && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {result.sessionId && (
                            <span
                              className="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-2 py-1"
                              title={result.sessionId}
                            >
                              <span className="text-[10px] uppercase tracking-[0.14em] text-gray-500">Session</span>
                              <span className="font-mono text-[11px] text-cyan-700">{shortRecordId(result.sessionId)}</span>
                            </span>
                          )}
                          {result.episodeId && (
                            <span
                              className="inline-flex items-center gap-2 rounded-md border border-violet-200 bg-violet-50 px-2 py-1"
                              title={result.episodeId}
                            >
                              <span className="text-[10px] uppercase tracking-[0.14em] text-gray-500">Episode</span>
                              <span className="font-mono text-[11px] text-violet-700">{shortRecordId(result.episodeId)}</span>
                            </span>
                          )}
                          {result.contextId && (
                            <span
                              className="inline-flex items-center gap-2 rounded-md border border-cyan-200 bg-cyan-50/80 px-2 py-1"
                              title={result.contextId}
                            >
                              <span className="text-[10px] uppercase tracking-[0.14em] text-gray-500">Context id</span>
                              <span className="font-mono text-[11px] text-cyan-800">{shortRecordId(result.contextId)}</span>
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-gray-500">
                      {new Date(result.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  
                  <div className="mb-3">
                    <p className="text-sm text-gray-600 mb-2">
                      <strong>Query:</strong> {result.query}
                    </p>
                    <div className="rounded-lg border border-gray-200 bg-white px-3 py-3">
                      {renderLlmMarkdown(String(result.response || ''), 'light')}
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Confidence: {(result.confidence * 100).toFixed(1)}%</span>
                    <span>Processing: {result.processingTime}</span>
                    <span>Chunks: {result.relevantChunks}{result.packedChunks && result.packedChunks !== result.relevantChunks ? ` (packed ${result.packedChunks})` : ''}</span>
                  </div>
                  {result.episodeId && (
                    <div className="mt-3 space-y-2 border-t border-[rgba(148,163,184,0.11)] pt-3">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-[#8b9cb0]">CKF closed loop</p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => submitFeedback(index, 'up', false)}
                          className="rounded-md border border-[rgba(62,207,155,0.35)] bg-[rgba(62,207,155,0.08)] px-2.5 py-1 text-xs text-[#9af0ca]"
                        >
                          Helpful
                        </button>
                        <button
                          type="button"
                          onClick={() => submitFeedback(index, 'down', false)}
                          className="rounded-md border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.08)] px-2.5 py-1 text-xs text-[#f3b4b0]"
                        >
                          Incorrect
                        </button>
                      </div>
                      <textarea
                        value={feedbackDrafts[index] || ''}
                        onChange={(e) => setFeedbackDrafts((prev) => ({ ...prev, [index]: e.target.value }))}
                        placeholder="Correction to write back into this fabric"
                        className="w-full rounded-md border px-2 py-1 text-xs"
                        rows={2}
                      />
                      <button
                        type="button"
                        onClick={() => submitFeedback(index, 'down', true)}
                        className="rounded-md bg-emerald-600 px-2 py-1 text-xs text-white"
                      >
                        Apply correction to fabric
                      </button>
                      {result.feedbackState && (
                        <p className="text-xs text-emerald-200">{result.feedbackState}</p>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Demo: with vs without Context Layer */}
      <div className="mt-8 overflow-hidden rounded-2xl border border-cyan-200/70 bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950 p-6 text-white shadow-xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Demo · same question, two modes</p>
            <h3 className="mt-2 text-lg font-semibold tracking-tight">Prove the Context Layer in one minute</h3>
            <p className="mt-1 text-sm text-slate-300">
              Run the claim once on Fabric only, then again with a published Context Layer attached. Watch the route and decision shift.
            </p>
          </div>
          <SparklesIcon className="h-8 w-8 shrink-0 text-cyan-300/80" />
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <button
            type="button"
            onClick={() => {
              setTestQuery(
                'Should we pay claim CLM-000008 for member MEM-0004 on plan PLN-CSNP-SILVER? Return a decision with rationale.'
              );
              setContextMode('fabric');
              setSelectedContextId('');
            }}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:border-white/25 hover:bg-white/10"
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Step 1</p>
            <p className="mt-1 text-sm font-semibold text-white">Load demo query · Fabric only</p>
            <p className="mt-1 text-xs text-slate-400">CLM-000008 · MEM-0004 · PLN-CSNP-SILVER</p>
          </button>
          <button
            type="button"
            disabled={!publishedContexts.length}
            onClick={() => {
              setTestQuery(
                'Should we pay claim CLM-000008 for member MEM-0004 on plan PLN-CSNP-SILVER? Return a decision with rationale.'
              );
              setContextMode('layer');
              if (publishedContexts[0]) setSelectedContextId(publishedContexts[0].id);
            }}
            className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-3 text-left transition hover:border-cyan-300/50 hover:bg-cyan-400/15 disabled:opacity-40"
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-300">Step 2</p>
            <p className="mt-1 text-sm font-semibold text-white">Same query · attach Context Layer</p>
            <p className="mt-1 text-xs text-cyan-200/80">
              {publishedContexts.length
                ? `Uses ${publishedContexts[0]?.name || 'published context'} → expect decision=pay`
                : 'Publish a context on this fabric first'}
            </p>
          </button>
        </div>
      </div>

      {/* Quick Test Examples */}
      <div className="mt-8 bg-white rounded-xl shadow-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <SparklesIcon className="w-5 h-5 mr-2 text-emerald-500" />
          Quick Test Examples
        </h3>
        
        {fabrics.length === 0 ? (
          <div className="text-center text-gray-500 py-4">
            <DocumentTextIcon className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p>No knowledge fabrics available. Create a fabric first to see test examples.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Fabric-specific examples */}
            {fabrics.map((fabric) => (
              <div key={fabric.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900">{fabric.name}</h4>
                  <span className="text-xs text-gray-500">
                    {fabric.document_count} docs, {fabric.total_chunks || 0} chunks
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {[
                    "What are the key stakeholders mentioned in this document?",
                    "Explain the main procedures described in this document",
                    "What are the important requirements or policies?",
                    "Summarize the main topics covered in this document",
                    "What are the key processes or workflows?",
                    "What are the main guidelines or best practices?"
                  ].map((example, index) => (
                    <button
                      key={index}
                      onClick={() => {
                        setSelectedFabric(fabric.id);
                        setTestQuery(example);
                      }}
                      className="text-left p-3 border border-gray-200 rounded-lg hover:border-emerald-300 hover:bg-emerald-50 transition-colors group"
                    >
                      <p className="text-sm text-gray-700 group-hover:text-emerald-700">{example}</p>
                      <p className="text-xs text-gray-500 mt-1">Click to select fabric & query</p>
                    </button>
                  ))}
                </div>
              </div>
            ))}
            
            {/* General examples */}
            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-3">General Knowledge Queries</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {[
                  "What is the main purpose of this document?",
                  "What are the key findings or conclusions?",
                  "What are the important dates or timelines mentioned?",
                  "What are the main challenges or issues discussed?",
                  "What are the recommendations or next steps?",
                  "What are the key metrics or data points?"
                ].map((example, index) => (
                  <button
                    key={index}
                    onClick={() => setTestQuery(example)}
                    className="text-left p-3 border border-gray-200 rounded-lg hover:border-emerald-300 hover:bg-emerald-50 transition-colors group"
                  >
                    <p className="text-sm text-gray-700 group-hover:text-emerald-700">{example}</p>
                    <p className="text-xs text-gray-500 mt-1">Click to set query only</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TestLLM; 