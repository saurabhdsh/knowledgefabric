import React, { useEffect, useMemo, useState } from 'react';
import { MagnifyingGlassIcon, SparklesIcon, DocumentTextIcon, ChartBarIcon } from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';

interface KnowledgeFabric {
  id: string;
  name: string;
  status: string;
  document_count: number;
  total_chunks?: number;
  model_status?: string;
}

interface GraphEntity {
  label: string;
  count?: number;
  frequency?: number;
}

interface GraphRelationship {
  relation: string;
  count?: number;
  frequency?: number;
}

interface AnalysisResults {
  fabricId: string;
  fabricName: string;
  analysisType: string;
  timestamp: string;
  metrics: {
    contextualScore: number;
    semanticScore: number;
    coherenceScore: number;
    completenessScore: number;
    overallScore: number;
  };
  insights: string[];
  recommendations: string[];
  topConcepts: { concept: string; relevance: number; frequency: number }[];
  topRelationships: { relation: string; frequency: number; strength: number }[];
}

const ContextAnalysis: React.FC = () => {
  const [selectedFabric, setSelectedFabric] = useState<string>('');
  const [analysisType, setAnalysisType] = useState<string>('contextual');
  const [analysisResults, setAnalysisResults] = useState<AnalysisResults | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [loadingFabrics, setLoadingFabrics] = useState(true);
  const [statusBanner, setStatusBanner] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  const selectedFabricDetails = useMemo(
    () => fabrics.find((f) => f.id === selectedFabric),
    [fabrics, selectedFabric]
  );

  const analysisTypes = [
    { id: 'contextual', name: 'Contextual Relevance', description: 'Analyze how well content relates to queries' },
    { id: 'semantic', name: 'Semantic Similarity', description: 'Measure semantic relationships between concepts' },
    { id: 'coherence', name: 'Content Coherence', description: 'Evaluate logical flow and consistency' },
    { id: 'completeness', name: 'Information Completeness', description: 'Assess coverage and comprehensiveness' },
  ];

  useEffect(() => {
    const fetchFabrics = async () => {
      setLoadingFabrics(true);
      try {
        const response = await apiRequest('api/v1/knowledge/');
        const data = await response.json();
        if (data.success && Array.isArray(data.data)) {
          setFabrics(data.data);
          if (selectedFabric && !data.data.some((f: KnowledgeFabric) => f.id === selectedFabric)) {
            setSelectedFabric('');
            setStatusBanner({
              type: 'error',
              message: 'Previously selected fabric is no longer available. Please select another fabric.',
            });
          }
        } else {
          setStatusBanner({
            type: 'error',
            message: data.message || 'Unable to fetch available fabrics.',
          });
        }
      } catch (error) {
        setStatusBanner({
          type: 'error',
          message: 'Unable to load available fabrics. Please verify backend is running.',
        });
      } finally {
        setLoadingFabrics(false);
      }
    };

    fetchFabrics();
  }, [selectedFabric]);

  const toFiniteNumber = (value: unknown, fallback = 0): number => {
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const clamp01 = (value: number, fallback = 0.5): number => {
    if (!Number.isFinite(value)) return fallback;
    return Math.max(0, Math.min(1, value));
  };

  const toScore = (value: unknown, divisor = 10): number => {
    const numeric = toFiniteNumber(value, 0);
    if (divisor <= 0) return 0.5;
    return clamp01(numeric / divisor, 0.5);
  };

  const handleRunAnalysis = async () => {
    if (!selectedFabric || !analysisType) {
      setStatusBanner({ type: 'info', message: 'Select a fabric and analysis type first.' });
      return;
    }

    setIsLoading(true);
    setStatusBanner(null);

    try {
      const response = await apiRequest(`api/v1/knowledge/${selectedFabric}/knowledge-graph?include_llm=true`);
      const payload = await response.json();
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || payload.message || 'Failed to analyze selected fabric.');
      }

      const analytics = payload.data.analytics || {};
      const topEntities: GraphEntity[] = analytics.top_entities || [];
      const topRelationships: GraphRelationship[] = analytics.top_relationships || [];
      const llmInsight = payload.data.llm_insight || {};

      const nodeCount = toFiniteNumber(analytics.node_count, 0);
      const edgeCount = toFiniteNumber(analytics.edge_count, 0);
      const isolatedNodes = toFiniteNumber(analytics.isolated_nodes, 0);
      const density = toFiniteNumber(analytics.graph_density, 0);
      const avgDegree = toFiniteNumber(analytics.avg_degree, 0);

      const conceptSeries = topEntities.map((entity) => ({
        concept: entity.label || 'Unknown Concept',
        frequency: toFiniteNumber(entity.count ?? entity.frequency, 0),
      }));
      const relationSeries = topRelationships.map((rel) => ({
        relation: rel.relation || 'related_to',
        frequency: toFiniteNumber(rel.count ?? rel.frequency, 0),
      }));
      const topConceptMax = Math.max(1, ...conceptSeries.map((c) => c.frequency));
      const topRelationMax = Math.max(1, ...relationSeries.map((r) => r.frequency));

      const semanticScore = toScore(avgDegree);
      const coherenceScore = toScore(density);
      const completenessScore = nodeCount > 0 ? clamp01((nodeCount - isolatedNodes) / nodeCount, 0.5) : 0.5;
      const contextualSignal = conceptSeries.length > 0 ? conceptSeries[0].frequency / Math.max(8, nodeCount) : 0;
      const contextualScore = clamp01(Math.max(0.55, Math.min(0.95, contextualSignal)), 0.55);
      const overallScore = clamp01((semanticScore + coherenceScore + completenessScore + contextualScore) / 4, 0.5);

      const nextResults: AnalysisResults = {
        fabricId: selectedFabric,
        fabricName: selectedFabricDetails?.name || payload.data.fabric_details?.name || selectedFabric,
        analysisType,
        timestamp: new Date().toISOString(),
        metrics: {
          contextualScore,
          semanticScore,
          coherenceScore,
          completenessScore,
          overallScore,
        },
        insights: [
          ...(llmInsight.summary ? [llmInsight.summary] : []),
          `Knowledge graph has ${nodeCount} entities and ${edgeCount} relationships.`,
          `Detected ${isolatedNodes} isolated entities requiring linkage review.`,
          `Average graph degree is ${avgDegree.toFixed(2)} with density ${density.toFixed(2)}.`,
        ],
        recommendations: llmInsight.recommendations || [
          'Review isolated entities and add missing relationship mappings.',
          'Improve extraction prompts to increase entity-relationship recall.',
          'Enrich source documents with more cross-domain terminology.',
        ],
        topConcepts: conceptSeries.map((entity) => ({
          concept: entity.concept,
          relevance: clamp01(Math.max(0.45, Math.min(0.98, entity.frequency / Math.max(5, topConceptMax))), 0.45),
          frequency: entity.frequency,
        })),
        topRelationships: relationSeries.map((rel) => ({
          relation: rel.relation,
          frequency: rel.frequency,
          strength: clamp01(Math.max(0.4, Math.min(0.98, rel.frequency / Math.max(4, topRelationMax))), 0.4),
        })),
      };

      setAnalysisResults(nextResults);
      setStatusBanner({ type: 'success', message: 'Context analysis completed using live fabric graph + OpenAI insight.' });
    } catch (error) {
      setStatusBanner({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to run context analysis.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.text-gray-300]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_textarea]:bg-[#10141d]/70 [&_textarea]:text-[#e8edf4] [&_textarea]:border-[rgba(148,163,184,0.2)] [&_textarea]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-12 h-12 bg-gradient-to-r from-orange-500 to-orange-600 rounded-xl flex items-center justify-center">
            <MagnifyingGlassIcon className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Context Analysis</h1>
            <p className="text-gray-600">Analyze the contextual relevance and semantic relationships in your knowledge fabrics</p>
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

      <div className="space-y-8">
        {/* Analysis Configuration - Horizontal */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
            <SparklesIcon className="w-5 h-5 mr-2 text-orange-500" />
            Analysis Configuration
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
            <div className="md:col-span-5">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Knowledge Fabric
              </label>
              <select
                value={selectedFabric}
                onChange={(e) => setSelectedFabric(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                disabled={loadingFabrics}
              >
                <option value="">
                  {loadingFabrics ? 'Loading fabrics...' : 'Choose a fabric...'}
                </option>
                {fabrics.map((fabric) => (
                  <option key={fabric.id} value={fabric.id}>
                    {fabric.name} ({fabric.document_count} docs, {fabric.total_chunks || 0} chunks) - {fabric.model_status || 'unknown'}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Analysis Type
              </label>
              <select
                value={analysisType}
                onChange={(e) => setAnalysisType(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
              >
                {analysisTypes.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-3">
              <button
                onClick={handleRunAnalysis}
                disabled={!selectedFabric || !analysisType || isLoading}
                className="w-full bg-gradient-to-r from-orange-500 to-orange-600 text-white px-6 py-2.5 rounded-lg font-medium hover:from-orange-600 hover:to-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center"
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                    Analyzing...
                  </>
                ) : (
                  <>
                    <ChartBarIcon className="w-5 h-5 mr-2" />
                    Run Analysis
                  </>
                )}
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {analysisTypes.find(t => t.id === analysisType)?.description}
          </p>
          {selectedFabricDetails && (
            <div className="mt-3 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-3 text-xs text-[#9fb0c5]">
              Using fabric: <span className="text-[#e8edf4] font-medium">{selectedFabricDetails.name}</span>
            </div>
          )}
        </div>

        {/* Analysis Results - Below */}
        <div>
          {!analysisResults ? (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="text-center text-gray-500 py-12">
                <MagnifyingGlassIcon className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-lg font-medium mb-2">No Analysis Results</h3>
                <p>Configure and run an analysis to see detailed insights about your knowledge fabric.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Overall Score */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Overall Analysis Score</h3>
                <div className="flex items-center space-x-4">
                  <div className="text-4xl font-bold text-orange-600">
                    {(analysisResults.metrics.overallScore * 100).toFixed(0)}%
                  </div>
                  <div className="flex-1">
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div 
                        className="bg-gradient-to-r from-orange-500 to-orange-600 h-3 rounded-full transition-all duration-500"
                        style={{ width: `${analysisResults.metrics.overallScore * 100}%` }}
                      ></div>
                    </div>
                    <p className="text-sm text-gray-600 mt-2">
                      {analysisResults.fabricName} - {analysisResults.analysisType}
                    </p>
                  </div>
                </div>
              </div>

              {/* Detailed Metrics */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Detailed Metrics</h3>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(analysisResults.metrics).map(([key, value]) => {
                    if (key === 'overallScore') return null;
                    return (
                      <div key={key} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-700 capitalize">
                            {key.replace('Score', ' Score')}
                          </span>
                          <span className="text-sm font-bold text-gray-900">
                            {(value as number * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-orange-500 h-2 rounded-full transition-all duration-500"
                            style={{ width: `${(value as number) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Relationship Strength Scatter Plot */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Relationship Strength Scatter Plot</h3>
                {analysisResults.topRelationships.length === 0 ? (
                  <p className="text-sm text-gray-500">No relationships available for plotting.</p>
                ) : (
                  <div className="space-y-4">
                    <div className="relative h-64 rounded-xl border border-gray-200 bg-gradient-to-b from-[#0f172a]/5 to-transparent overflow-hidden">
                      <div className="absolute inset-0 opacity-60" style={{
                        backgroundImage:
                          'linear-gradient(to right, rgba(148,163,184,0.25) 1px, transparent 1px), linear-gradient(to top, rgba(148,163,184,0.25) 1px, transparent 1px)',
                        backgroundSize: '32px 32px',
                      }} />
                      <div className="absolute left-3 top-2 text-[10px] text-gray-500 uppercase tracking-[0.14em]">Strength</div>
                      <div className="absolute right-3 bottom-2 text-[10px] text-gray-500 uppercase tracking-[0.14em]">Frequency</div>
                      {analysisResults.topRelationships.slice(0, 8).map((item, index) => {
                        const x = Math.max(8, Math.min(92, item.strength * 100));
                        const y = Math.max(8, Math.min(92, (item.frequency / Math.max(1, analysisResults.topRelationships[0]?.frequency || 1)) * 100));
                        const size = 10 + (item.strength * 18);
                        return (
                          <div
                            key={`${item.relation}-${index}`}
                            className="absolute -translate-x-1/2 -translate-y-1/2 group cursor-pointer"
                            style={{ left: `${x}%`, bottom: `${y}%` }}
                            title={`${item.relation} • strength ${Math.round(item.strength * 100)}% • frequency ${item.frequency}`}
                          >
                            <div
                              className="rounded-full bg-gradient-to-r from-cyan-500 to-indigo-500 shadow-[0_0_18px_rgba(56,189,248,0.35)] transition-transform duration-200 group-hover:scale-110"
                              style={{ width: `${size}px`, height: `${size}px` }}
                            />
                            <div className="absolute left-1/2 -translate-x-1/2 mt-1 min-w-max text-[10px] font-medium text-gray-700 opacity-0 group-hover:opacity-100 transition-opacity">
                              {item.relation}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {analysisResults.topRelationships.slice(0, 6).map((item, index) => (
                        <div key={`${item.relation}-legend-${index}`} className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2">
                          <span className="text-xs text-gray-700 truncate pr-2">{item.relation}</span>
                          <span className="text-xs font-semibold text-indigo-600">{Math.round(item.strength * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Insights and Recommendations */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                    <DocumentTextIcon className="w-5 h-5 mr-2 text-orange-500" />
                    Key Insights
                  </h3>
                  <ul className="space-y-2">
                    {analysisResults.insights.map((insight: string, index: number) => (
                      <li key={index} className="flex items-start">
                        <div className="w-2 h-2 bg-orange-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                        <span className="text-sm text-gray-700">{insight}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-white rounded-xl shadow-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                    <SparklesIcon className="w-5 h-5 mr-2 text-orange-500" />
                    Recommendations
                  </h3>
                  <ul className="space-y-2">
                    {analysisResults.recommendations.map((rec: string, index: number) => (
                      <li key={index} className="flex items-start">
                        <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                        <span className="text-sm text-gray-700">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Top Concepts - Signature Cards */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Concepts Signature View</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {analysisResults.topConcepts.slice(0, 6).map((concept: any, index: number) => {
                    const score = Math.round(concept.relevance * 100);
                    return (
                      <div
                        key={index}
                        className="relative overflow-hidden rounded-xl border border-[rgba(148,163,184,0.2)] p-4 bg-[linear-gradient(145deg,rgba(15,23,42,0.8),rgba(30,41,59,0.45))] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
                      >
                        <div className="absolute right-3 top-3 text-[10px] px-2 py-1 rounded-full border border-[rgba(251,146,60,0.35)] bg-orange-500/15 text-orange-300 font-semibold tracking-[0.08em]">
                          C{index + 1}
                        </div>
                        <div className="pr-16">
                          <div className="font-semibold text-[#e8edf4]">{concept.concept}</div>
                          <div className="mt-1 text-xs text-[#8b9cb0]">Frequency: {concept.frequency} mentions</div>
                        </div>
                        <div className="mt-4">
                          <div className="flex items-center justify-between text-xs text-[#8b9cb0] mb-1">
                            <span>Impact Signature</span>
                            <span className="font-semibold text-orange-300">{score}%</span>
                          </div>
                          <div className="h-2.5 rounded-full bg-[#0f1728] border border-[rgba(148,163,184,0.16)] overflow-hidden">
                            <div
                              className="h-2.5 rounded-full bg-gradient-to-r from-orange-400 via-amber-400 to-pink-400 shadow-[0_0_16px_rgba(251,146,60,0.45)]"
                              style={{ width: `${score}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ContextAnalysis; 