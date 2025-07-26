import React, { useState } from 'react';
import {
  DocumentTextIcon,
  ServerIcon,
  CpuChipIcon,
  CheckCircleIcon,
  ArrowRightIcon,
  SparklesIcon,
  BeakerIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';
import PDFUpload from '../components/PDFUpload';
import KnowledgeFabricProgress from '../components/KnowledgeFabricProgress';

interface KnowledgeOption {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<any>;
  features: string[];
  color: string;
  gradient: string;
}

const Knowledge: React.FC = () => {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showPDFUpload, setShowPDFUpload] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [showProgress, setShowProgress] = useState(false);
  const [createdFabricId, setCreatedFabricId] = useState<string>('');

  const knowledgeOptions: KnowledgeOption[] = [
    {
      id: 'pdf',
      title: 'Upload PDF Documents',
      description: 'Upload and process PDF files to extract knowledge and create embeddings',
      icon: DocumentTextIcon,
      features: [
        'Extract text from PDF documents',
        'Automatic chunking and processing',
        'Generate embeddings for semantic search',
        'Support for multiple PDF files',
        'Real-time processing status'
      ],
      color: 'blue',
      gradient: 'from-blue-500 to-blue-600'
    },
    {
      id: 'database',
      title: 'Connect to Database',
      description: 'Connect to various databases to extract structured knowledge',
      icon: ServerIcon,
      features: [
        'Support for MongoDB, PostgreSQL, MySQL',
        'Automatic schema detection',
        'Query optimization and indexing',
        'Real-time data synchronization',
        'Secure connection management'
      ],
      color: 'green',
      gradient: 'from-green-500 to-green-600'
    },
    {
      id: 'hybrid',
      title: 'Hybrid Approach',
      description: 'Combine PDF documents with database connections for comprehensive knowledge',
      icon: BeakerIcon,
      features: [
        'Merge PDF and database knowledge',
        'Cross-reference capabilities',
        'Enhanced search accuracy',
        'Unified knowledge graph',
        'Advanced analytics and insights'
      ],
      color: 'purple',
      gradient: 'from-purple-500 to-purple-600'
    }
  ];

  const handleCreateKnowledge = async () => {
    if (!selectedOption) return;
    
    if (selectedOption === 'pdf') {
      setShowPDFUpload(true);
      return;
    }
    
    setIsCreating(true);
    
    // Simulate API call for other options
    setTimeout(() => {
      setIsCreating(false);
      // Here you would make actual API calls to create knowledge fabric
      console.log(`Creating knowledge fabric with option: ${selectedOption}`);
    }, 2000);
  };

  const handlePDFUploadComplete = async (files: File[]) => {
    setUploadedFiles(files);
    setShowPDFUpload(false);
    
    // Show the progress tracking
    setShowProgress(true);
  };

  const handleProgressComplete = (fabricId: string) => {
    setCreatedFabricId(fabricId);
    setShowProgress(false);
    setSelectedOption(null);
    
    // Show success message with fabric details
    const successMessage = `🎉 Knowledge Fabric Created Successfully!

Fabric ID: ${fabricId}
Status: Active
Training: Completed

You can now view your fabric in the "Available Fabrics" tab with real statistics including:
• Document count
• Chunks count  
• Embedding count
• Training status
• Creation date`;
    
    alert(successMessage);
    
    console.log('Knowledge fabric created successfully:', fabricId);
  };

  const handleProgressError = (error: string) => {
    setShowProgress(false);
    console.error('Knowledge fabric creation failed:', error);
  };

  const handlePDFUploadCancel = () => {
    setShowPDFUpload(false);
    setSelectedOption(null);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* PDF Upload Modal */}
      {showPDFUpload && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <PDFUpload
              onUploadComplete={handlePDFUploadComplete}
              onCancel={handlePDFUploadCancel}
            />
          </div>
        </div>
      )}

      {/* Knowledge Fabric Progress Modal */}
      <KnowledgeFabricProgress
        isVisible={showProgress}
        onComplete={handleProgressComplete}
        onError={handleProgressError}
        uploadedFiles={uploadedFiles.map(f => f.name)}
      />

      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex items-center justify-center mb-4">
          <div className="p-3 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full">
            <SparklesIcon className="h-8 w-8 text-white" />
          </div>
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Create Knowledge Fabric
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          Choose your preferred method to build a comprehensive knowledge base that powers your AI agents
        </p>
      </div>

      {/* Options Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
        {knowledgeOptions.map((option) => (
          <div
            key={option.id}
            className={`relative group cursor-pointer transition-all duration-300 transform hover:scale-105 ${
              selectedOption === option.id
                ? 'ring-4 ring-indigo-500 ring-opacity-50'
                : 'hover:shadow-2xl'
            }`}
            onClick={() => setSelectedOption(option.id)}
          >
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8 h-full">
              {/* Icon */}
              <div className={`w-16 h-16 bg-gradient-to-r ${option.gradient} rounded-xl flex items-center justify-center mb-6`}>
                <option.icon className="h-8 w-8 text-white" />
              </div>

              {/* Content */}
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                {option.title}
              </h3>
              <p className="text-gray-600 mb-6 leading-relaxed">
                {option.description}
              </p>

              {/* Features */}
              <div className="space-y-3">
                {option.features.map((feature, index) => (
                  <div key={index} className="flex items-center">
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-3 flex-shrink-0" />
                    <span className="text-sm text-gray-700">{feature}</span>
                  </div>
                ))}
              </div>

              {/* Selection Indicator */}
              {selectedOption === option.id && (
                <div className="absolute top-4 right-4">
                  <div className="w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center">
                    <CheckCircleIcon className="h-5 w-5 text-white" />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Action Section */}
      {selectedOption && (
        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-8 border border-indigo-100">
          <div className="text-center">
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              Ready to Create Your Knowledge Fabric?
            </h3>
            <p className="text-gray-600 mb-8 max-w-2xl mx-auto">
              Your knowledge fabric will be created in the local vector database and the model will be automatically trained for optimal performance.
            </p>
            
            <div className="flex items-center justify-center space-x-4">
              <button
                onClick={handleCreateKnowledge}
                disabled={isCreating}
                className={`px-8 py-4 bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center space-x-2 ${
                  isCreating ? 'opacity-75 cursor-not-allowed' : ''
                }`}
              >
                {isCreating ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>Creating Knowledge Fabric...</span>
                  </>
                ) : (
                  <>
                    <CpuChipIcon className="h-5 w-5" />
                    <span>Create Knowledge Fabric</span>
                    <ArrowRightIcon className="h-5 w-5" />
                  </>
                )}
              </button>
            </div>

            {/* Progress Steps */}
            {isCreating && (
              <div className="mt-8">
                <div className="flex items-center justify-center space-x-8">
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                      <CheckCircleIcon className="h-5 w-5 text-white" />
                    </div>
                    <span className="ml-2 text-sm font-medium text-gray-700">Processing Data</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    </div>
                    <span className="ml-2 text-sm font-medium text-gray-700">Creating Embeddings</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
                      <CpuChipIcon className="h-5 w-5 text-gray-500" />
                    </div>
                    <span className="ml-2 text-sm font-medium text-gray-500">Training Model</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Info Section */}
      <div className="mt-12 bg-white rounded-2xl shadow-lg p-8 border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <ServerIcon className="h-6 w-6 text-blue-600" />
            </div>
            <h4 className="font-semibold text-gray-900 mb-2">Local Vector Database</h4>
            <p className="text-sm text-gray-600">
              All knowledge is stored locally in ChromaDB for privacy and performance
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <CpuChipIcon className="h-6 w-6 text-green-600" />
            </div>
            <h4 className="font-semibold text-gray-900 mb-2">BERT Model Training</h4>
            <p className="text-sm text-gray-600">
              Local BERT model is trained on your data for contextual understanding
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <GlobeAltIcon className="h-6 w-6 text-purple-600" />
            </div>
            <h4 className="font-semibold text-gray-900 mb-2">Agent Integration</h4>
            <p className="text-sm text-gray-600">
              Ready-to-use API endpoints for your AI agents to access knowledge
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Knowledge; 