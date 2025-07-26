import React, { useState, useEffect } from 'react';
import { ChatBubbleLeftRightIcon, SparklesIcon, DocumentTextIcon, CpuChipIcon } from '@heroicons/react/24/outline';

interface KnowledgeFabric {
  id: string;
  name: string;
  status: string;
  document_count: number;
  total_chunks?: number;
  created_at: string;
  model_status: string;
}

const TestLLM: React.FC = () => {
  const [selectedFabric, setSelectedFabric] = useState<string>('');
  const [selectedLLM, setSelectedLLM] = useState<string>('openai');
  const [testQuery, setTestQuery] = useState<string>('');
  const [testResults, setTestResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [loadingFabrics, setLoadingFabrics] = useState(true);

  // Fetch available fabrics on component mount
  useEffect(() => {
    const fetchFabrics = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/v1/knowledge/');
        const data = await response.json();
        
        if (data.success && data.data) {
          setFabrics(data.data);
        } else {
          console.error('Failed to fetch fabrics:', data.message);
        }
      } catch (error) {
        console.error('Error fetching fabrics:', error);
      } finally {
        setLoadingFabrics(false);
      }
    };

    fetchFabrics();
  }, []);

  const handleTestQuery = async () => {
    if (!selectedFabric || !testQuery.trim() || !selectedLLM) return;

    setIsLoading(true);
    
    try {
      const response = await fetch(`http://localhost:8000/api/v1/knowledge/query/${selectedFabric}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: testQuery,
          llm_provider: selectedLLM
        })
      });

      const data = await response.json();
      
      const result = {
        fabricId: selectedFabric,
        llmProvider: selectedLLM,
        query: testQuery,
        response: data.success ? data.data.answer : 'Sorry, I encountered an error. Please try again.',
        confidence: data.success ? data.data.confidence || 0.85 : 0.0,
        timestamp: new Date().toISOString(),
        relevantChunks: data.success ? data.data.relevant_chunks || 3 : 0,
        processingTime: data.success ? data.data.processing_time || '1.2s' : '0s'
      };

      setTestResults(prev => [result, ...prev]);
    } catch (error) {
      const errorResult = {
        fabricId: selectedFabric,
        llmProvider: selectedLLM,
        query: testQuery,
        response: 'Sorry, I encountered an error. Please try again.',
        confidence: 0.0,
        timestamp: new Date().toISOString(),
        relevantChunks: 0,
        processingTime: '0s'
      };
      setTestResults(prev => [errorResult, ...prev]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-12 h-12 bg-gradient-to-r from-emerald-500 to-emerald-600 rounded-xl flex items-center justify-center">
            <ChatBubbleLeftRightIcon className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Test with LLM</h1>
            <p className="text-gray-600">Test your knowledge fabrics with advanced LLM capabilities</p>
          </div>
        </div>
      </div>

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
                  onChange={(e) => setSelectedFabric(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  disabled={loadingFabrics}
                >
                  <option value="">
                    {loadingFabrics ? 'Loading fabrics...' : 'Choose a fabric...'}
                  </option>
                  {fabrics.map((fabric) => (
                    <option key={fabric.id} value={fabric.id}>
                      {fabric.name} ({fabric.document_count} docs, {fabric.total_chunks || 0} chunks) - {fabric.model_status}
                    </option>
                  ))}
                </select>
                {selectedFabric && (
                  <div className="mt-2 p-2 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <p className="text-xs text-emerald-700">
                      <strong>Selected:</strong> {fabrics.find(f => f.id === selectedFabric)?.name}
                    </p>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select LLM Provider
                </label>
                <select
                  value={selectedLLM}
                  onChange={(e) => setSelectedLLM(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  <option value="openai">OpenAI GPT-4</option>
                  <option value="gemini" disabled>Gemini (Coming Soon)</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  {selectedLLM === 'openai' ? 'Using OpenAI GPT-4 for advanced reasoning' : 'Gemini integration coming soon'}
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
              disabled={!selectedFabric || !testQuery.trim() || isLoading}
              className="w-full bg-gradient-to-r from-emerald-500 to-emerald-600 text-white px-6 py-3 rounded-lg font-medium hover:from-emerald-600 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center"
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  Testing...
                </>
              ) : (
                <>
                  <CpuChipIcon className="w-5 h-5 mr-2" />
                  Run Test
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
                <p>No test results yet. Run a test to see results here.</p>
              </div>
            ) : (
              testResults.map((result, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-700">
                        {fabrics.find(f => f.id === result.fabricId)?.name || 'Unknown Fabric'}
                      </span>
                      <span className="px-2 py-1 text-xs bg-emerald-100 text-emerald-700 rounded-full">
                        {result.llmProvider?.toUpperCase() || 'LLM'}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(result.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  
                  <div className="mb-3">
                    <p className="text-sm text-gray-600 mb-1">
                      <strong>Query:</strong> {result.query}
                    </p>
                    <p className="text-sm text-gray-800 whitespace-pre-line">
                      {result.response}
                    </p>
                  </div>
                  
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Confidence: {(result.confidence * 100).toFixed(1)}%</span>
                    <span>Processing: {result.processingTime}</span>
                    <span>Chunks: {result.relevantChunks}</span>
                  </div>
                </div>
              ))
            )}
          </div>
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