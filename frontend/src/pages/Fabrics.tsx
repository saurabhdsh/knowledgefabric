import React, { useState, useEffect } from 'react';
import {
  DocumentTextIcon,
  ServerIcon,
  CpuChipIcon,
  CheckCircleIcon,
  SparklesIcon,
  BeakerIcon,
  GlobeAltIcon,
  TrashIcon,
  EyeIcon,
  ArrowDownTrayIcon,
  PlayIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  CubeIcon,
} from '@heroicons/react/24/outline';
import FabricEndpointsDialog from '../components/FabricEndpointsDialog';

interface KnowledgeFabric {
  id: string;
  name: string;
  source_type: string;
  description?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  document_count: number;
  total_chunks?: number;
  status: string;
  model_status?: string;
  last_training?: string;
}

const Fabrics: React.FC = () => {
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEndpointsDialog, setShowEndpointsDialog] = useState(false);
  const [selectedFabricForEndpoints, setSelectedFabricForEndpoints] = useState<KnowledgeFabric | null>(null);

  // Fetch real data from API
  useEffect(() => {
    const fetchFabrics = async () => {
      try {
        setLoading(true);
        const response = await fetch('http://localhost:8000/api/v1/knowledge/');
        
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.data) {
            setFabrics(data.data);
          } else {
            console.error('Failed to fetch fabrics:', data.message);
            setFabrics([]);
          }
        } else {
          console.error('Failed to fetch fabrics');
          setFabrics([]);
        }
      } catch (error) {
        console.error('Error fetching fabrics:', error);
        setFabrics([]);
      } finally {
        setLoading(false);
      }
    };

    fetchFabrics();
    
    // Refresh data every 10 seconds to get updated training status
    const interval = setInterval(fetchFabrics, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/v1/knowledge/');
      
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setFabrics(data.data);
        }
      }
    } catch (error) {
      console.error('Error refreshing fabrics:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'training':
        return 'bg-blue-100 text-blue-800';
      case 'error':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getModelStatusColor = (status?: string) => {
    switch (status) {
      case 'trained':
        return 'bg-green-100 text-green-800';
      case 'training':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getSourceTypeIcon = (sourceType: string) => {
    switch (sourceType) {
      case 'pdf':
        return <DocumentTextIcon className="h-5 w-5" />;
      case 'database':
        return <ServerIcon className="h-5 w-5" />;
      case 'mixed':
        return <BeakerIcon className="h-5 w-5" />;
      default:
        return <GlobeAltIcon className="h-5 w-5" />;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleViewFabric = (fabric: KnowledgeFabric) => {
    // View fabric details - can be implemented later
    console.log('View fabric:', fabric);
  };

  const handleDeleteFabric = async (fabricId: string) => {
    if (window.confirm('Are you sure you want to delete this knowledge fabric?')) {
      try {
        // API call to delete fabric
        const response = await fetch(`http://localhost:8000/api/v1/knowledge/${fabricId}`, {
          method: 'DELETE'
        });
        
        if (response.ok) {
          setFabrics(prev => prev.filter(f => f.id !== fabricId));
        }
      } catch (error) {
        console.error('Error deleting fabric:', error);
      }
    }
  };

  const handleExportFabric = async (fabricId: string) => {
    try {
      // API call to export fabric
      const response = await fetch(`http://localhost:8000/api/v1/knowledge/${fabricId}/export`);
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `fabric_${fabricId}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Error exporting fabric:', error);
    }
  };

  const handleValidateFabric = async (fabricId: string, fabricName: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/knowledge/validate-knowledge/${fabricId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          questions: [
            "What is this document about?",
            "What are the key points discussed?",
            "What is the main purpose?"
          ]
        }),
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          const data = result.data;
          alert(`✅ Knowledge Validation Results for ${fabricName}:\n\n` +
                `📊 Validation Score: ${(data.validation_score * 100).toFixed(1)}%\n` +
                `🎯 Assessment: ${data.overall_assessment}\n` +
                `❓ Questions Tested: ${data.test_questions}\n\n` +
                `📝 Sample Response:\n"${data.results[0].response}"`);
        } else {
          alert(`❌ Validation failed: ${result.message}`);
        }
      } else {
        alert('❌ Failed to validate knowledge fabric');
      }
    } catch (error) {
      console.error('Error validating fabric:', error);
      alert('❌ Error validating knowledge fabric');
    }
  };

  const handleUseFabric = (fabric: KnowledgeFabric) => {
    setSelectedFabricForEndpoints(fabric);
    setShowEndpointsDialog(true);
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading knowledge fabrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex items-center justify-center mb-4">
          <div className="p-3 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full">
            <SparklesIcon className="h-8 w-8 text-white" />
          </div>
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Available Knowledge Fabrics
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-6">
          Manage and explore your created knowledge fabrics
        </p>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ArrowPathIcon className="h-5 w-5 mr-2" />
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-3 bg-blue-100 rounded-lg">
              <SparklesIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Fabrics</p>
              <p className="text-2xl font-bold text-gray-900">{fabrics.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-3 bg-green-100 rounded-lg">
              <CheckCircleIcon className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Active</p>
              <p className="text-2xl font-bold text-gray-900">
                {fabrics.filter(f => f.status === 'active').length}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-3 bg-purple-100 rounded-lg">
              <CpuChipIcon className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Trained Models</p>
              <p className="text-2xl font-bold text-gray-900">
                {fabrics.filter(f => f.model_status === 'trained').length}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-3 bg-orange-100 rounded-lg">
              <DocumentTextIcon className="h-6 w-6 text-orange-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Documents</p>
              <p className="text-2xl font-bold text-gray-900">
                {fabrics.reduce((sum, f) => sum + f.document_count, 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center">
            <div className="p-3 bg-teal-100 rounded-lg">
              <CubeIcon className="h-6 w-6 text-teal-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Chunks</p>
              <p className="text-2xl font-bold text-gray-900">
                {fabrics.reduce((sum, f) => sum + (f.total_chunks || 0), 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Fabrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {fabrics.map((fabric) => (
          <div
            key={fabric.id}
            className="bg-white rounded-xl shadow-lg border border-gray-200 hover:shadow-xl transition-shadow duration-300"
          >
            <div className="p-6">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-indigo-100 rounded-lg">
                    {getSourceTypeIcon(fabric.source_type)}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {fabric.name}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {fabric.source_type.toUpperCase()}
                    </p>
                  </div>
                </div>
                
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleViewFabric(fabric)}
                    className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                    title="View Details"
                  >
                    <EyeIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => handleExportFabric(fabric.id)}
                    className="p-2 text-gray-400 hover:text-green-600 transition-colors"
                    title="Export"
                  >
                    <ArrowDownTrayIcon className="h-5 w-5" />
                  </button>
                                     <button
                     onClick={() => handleValidateFabric(fabric.id, fabric.name)}
                     className="p-2 text-gray-400 hover:text-purple-600 transition-colors"
                     title="Validate Knowledge"
                   >
                     <MagnifyingGlassIcon className="h-5 w-5" />
                   </button>
                  <button
                    onClick={() => handleDeleteFabric(fabric.id)}
                    className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                    title="Delete"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {/* Description */}
              {fabric.description && (
                <p className="text-gray-600 mb-4 line-clamp-2">
                  {fabric.description}
                </p>
              )}

              {/* Tags */}
              {fabric.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {fabric.tags.slice(0, 3).map((tag, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                  {fabric.tags.length > 3 && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full">
                      +{fabric.tags.length - 3} more
                    </span>
                  )}
                </div>
              )}

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <p className="text-xs text-gray-500">Documents</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {fabric.document_count.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Chunks</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {fabric.total_chunks?.toLocaleString() || '0'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Created</p>
                  <p className="text-sm font-medium text-gray-900">
                    {formatDate(fabric.created_at)}
                  </p>
                </div>
              </div>

              {/* Status */}
              <div className="flex items-center justify-between">
                <span className={`px-3 py-1 text-xs font-medium rounded-full ${getStatusColor(fabric.status)}`}>
                  {fabric.status}
                </span>
                {fabric.model_status && (
                  <span className={`px-3 py-1 text-xs font-medium rounded-full ${getModelStatusColor(fabric.model_status)}`}>
                    {fabric.model_status}
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="px-6 pb-6">
              <button 
                onClick={() => handleUseFabric(fabric)}
                className="w-full bg-gradient-to-r from-indigo-500 to-purple-600 text-white py-2 px-4 rounded-lg font-medium hover:from-indigo-600 hover:to-purple-700 transition-all duration-200 flex items-center justify-center space-x-2"
              >
                <PlayIcon className="h-4 w-4" />
                <span>Use Fabric</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {fabrics.length === 0 && (
        <div className="text-center py-12">
          <div className="mx-auto w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mb-6">
            <SparklesIcon className="h-12 w-12 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Knowledge Fabrics Yet</h3>
          <p className="text-gray-600 mb-6">
            Create your first knowledge fabric by uploading documents or connecting to databases.
          </p>
          <button className="bg-indigo-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-indigo-700 transition-colors">
            Create Knowledge Fabric
          </button>
        </div>
      )}

      {/* Dialogs */}
      {selectedFabricForEndpoints && (
        <FabricEndpointsDialog
          isOpen={showEndpointsDialog}
          onClose={() => {
            setShowEndpointsDialog(false);
            setSelectedFabricForEndpoints(null);
          }}
          fabricId={selectedFabricForEndpoints.id}
          fabricName={selectedFabricForEndpoints.name}
        />
      )}
    </div>
  );
};

export default Fabrics; 