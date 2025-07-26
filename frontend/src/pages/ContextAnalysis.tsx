import React, { useState } from 'react';
import { MagnifyingGlassIcon, SparklesIcon, DocumentTextIcon, ChartBarIcon } from '@heroicons/react/24/outline';

const ContextAnalysis: React.FC = () => {
  const [selectedFabric, setSelectedFabric] = useState<string>('');
  const [analysisType, setAnalysisType] = useState<string>('contextual');
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  const mockFabrics = [
    { id: 'fabric_1', name: 'Knowledge_Fabric_1', status: 'Trained', documents: 3, chunks: 45 },
    { id: 'fabric_2', name: 'Claims_Processing_Guide', status: 'Trained', documents: 2, chunks: 32 },
    { id: 'fabric_3', name: 'Policy_Documentation', status: 'Training', documents: 1, chunks: 18 },
  ];

  const analysisTypes = [
    { id: 'contextual', name: 'Contextual Relevance', description: 'Analyze how well content relates to queries' },
    { id: 'semantic', name: 'Semantic Similarity', description: 'Measure semantic relationships between concepts' },
    { id: 'coherence', name: 'Content Coherence', description: 'Evaluate logical flow and consistency' },
    { id: 'completeness', name: 'Information Completeness', description: 'Assess coverage and comprehensiveness' },
  ];

  const handleRunAnalysis = async () => {
    if (!selectedFabric || !analysisType) return;

    setIsLoading(true);
    
    // Simulate API call
    setTimeout(() => {
      const mockResults = {
        fabricId: selectedFabric,
        fabricName: mockFabrics.find(f => f.id === selectedFabric)?.name,
        analysisType: analysisType,
        timestamp: new Date().toISOString(),
        metrics: {
          contextualScore: 0.87,
          semanticScore: 0.92,
          coherenceScore: 0.78,
          completenessScore: 0.85,
          overallScore: 0.86
        },
        insights: [
          "High semantic similarity between related concepts",
          "Good contextual relevance for most queries",
          "Some gaps in information completeness",
          "Strong coherence in policy-related content"
        ],
        recommendations: [
          "Add more examples to improve completeness",
          "Enhance cross-references between related topics",
          "Consider expanding coverage of edge cases"
        ],
        topConcepts: [
          { concept: "Claims Processing", relevance: 0.95, frequency: 23 },
          { concept: "Policy Requirements", relevance: 0.88, frequency: 18 },
          { concept: "Stakeholder Roles", relevance: 0.82, frequency: 15 },
          { concept: "Workflow Procedures", relevance: 0.79, frequency: 12 }
        ]
      };

      setAnalysisResults(mockResults);
      setIsLoading(false);
    }, 3000);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Analysis Configuration */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
              <SparklesIcon className="w-5 h-5 mr-2 text-orange-500" />
              Analysis Configuration
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Knowledge Fabric
                </label>
                <select
                  value={selectedFabric}
                  onChange={(e) => setSelectedFabric(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                >
                  <option value="">Choose a fabric...</option>
                  {mockFabrics.map((fabric) => (
                    <option key={fabric.id} value={fabric.id}>
                      {fabric.name} ({fabric.documents} docs, {fabric.chunks} chunks)
                    </option>
                  ))}
                </select>
              </div>

              <div>
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
                <p className="text-xs text-gray-500 mt-1">
                  {analysisTypes.find(t => t.id === analysisType)?.description}
                </p>
              </div>

              <button
                onClick={handleRunAnalysis}
                disabled={!selectedFabric || !analysisType || isLoading}
                className="w-full bg-gradient-to-r from-orange-500 to-orange-600 text-white px-6 py-3 rounded-lg font-medium hover:from-orange-600 hover:to-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center"
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
        </div>

        {/* Analysis Results */}
        <div className="lg:col-span-2">
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

              {/* Top Concepts */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Concepts</h3>
                <div className="space-y-3">
                  {analysisResults.topConcepts.map((concept: any, index: number) => (
                    <div key={index} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                      <div>
                        <span className="font-medium text-gray-900">{concept.concept}</span>
                        <p className="text-xs text-gray-500">Frequency: {concept.frequency} mentions</p>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold text-orange-600">
                          {(concept.relevance * 100).toFixed(0)}%
                        </span>
                        <p className="text-xs text-gray-500">Relevance</p>
                      </div>
                    </div>
                  ))}
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