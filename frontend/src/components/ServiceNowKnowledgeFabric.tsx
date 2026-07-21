import React, { useState } from 'react';
import { apiRequest } from '../utils/api';
import {
  DocumentArrowUpIcon,
  CloudIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface FabricGuardrails {
  data_classification: 'public' | 'internal' | 'confidential' | 'restricted';
  compliance_tags: string[];
  pii_fields: string[];
  enforce_masking: boolean;
  encryption_at_rest: boolean;
  encryption_in_transit: boolean;
  row_level_security: boolean;
  approved_roles: string[];
}

interface ServiceNowKnowledgeFabricProps {
  isVisible: boolean;
  onCancel: () => void;
  onComplete: (fabricId: string) => void;
  weaveDomain?: string;
  connectorProfile?: string | null;
  guardrails?: FabricGuardrails;
}

const ServiceNowKnowledgeFabric: React.FC<ServiceNowKnowledgeFabricProps> = ({
  isVisible,
  onCancel,
  onComplete,
  weaveDomain = 'general',
  connectorProfile,
  guardrails,
}) => {
  const [selectedMethod, setSelectedMethod] = useState<'file' | 'connection' | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [connectionData, setConnectionData] = useState({
    instanceUrl: '',
    username: '',
    password: '',
    tableName: '',
    query: ''
  });
  const [isProcessing, setIsProcessing] = useState(false);

  if (!isVisible) return null;

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    const validFiles = files.filter(file => 
      file.type === 'text/csv' || 
      file.type === 'application/vnd.ms-excel' ||
      file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    setUploadedFiles(validFiles);
  };

  const handleConnectionChange = (field: string, value: string) => {
    setConnectionData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleCreateFabric = async () => {
    if (!selectedMethod) return;

    setIsProcessing(true);

    try {
      let fabricId = '';
      
      if (selectedMethod === 'file') {
        // Handle file upload
        if (uploadedFiles.length === 0) {
          alert('Please select at least one file');
          setIsProcessing(false);
          return;
        }

        const formData = new FormData();
        uploadedFiles.forEach(file => {
          formData.append('files', file);
        });
        formData.append('source_type', 'servicenow_file');
        formData.append('weave_domain', weaveDomain);
        if (connectorProfile) formData.append('connector_profile', connectorProfile);
        if (guardrails) formData.append('guardrails', JSON.stringify(guardrails));

        const response = await apiRequest('api/v1/knowledge/create-servicenow-fabric', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error('Failed to create ServiceNow fabric from files');
        }

        const result = await response.json();
        fabricId = result.data?.source_id || `servicenow_file_${Date.now()}`;
      } else {
        // Handle direct connection
        if (!connectionData.instanceUrl || !connectionData.username || !connectionData.password) {
          alert('Please fill in all required connection fields');
          setIsProcessing(false);
          return;
        }

        const response = await apiRequest('api/v1/knowledge/create-servicenow-fabric', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            source_type: 'servicenow_connection',
            connection_data: connectionData,
            weave_domain: weaveDomain,
            ...(connectorProfile ? { connector_profile: connectorProfile } : {}),
            ...(guardrails ? { guardrails } : {}),
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to create ServiceNow fabric from connection');
        }

        const result = await response.json();
        fabricId = result.data?.source_id || `servicenow_conn_${Date.now()}`;
      }

      onComplete(fabricId);
    } catch (error) {
      console.error('Error creating ServiceNow fabric:', error);
      alert(`Error creating ServiceNow fabric: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50">
      <div className="bg-[#10141d]/92 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-[rgba(148,163,184,0.2)] text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_textarea]:bg-[#10141d]/70 [&_textarea]:text-[#e8edf4] [&_textarea]:border-[rgba(148,163,184,0.2)] [&_textarea]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center">
              <CloudIcon className="h-8 w-8 text-orange-500 mr-3" />
              Create ServiceNow Knowledge Fabric
            </h2>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          <div className="space-y-6">
            {/* Method Selection */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Choose Import Method</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                  onClick={() => setSelectedMethod('file')}
                  className={`p-6 border-2 rounded-lg text-left transition-all ${
                    selectedMethod === 'file'
                      ? 'border-orange-500 bg-orange-50'
                      : 'border-gray-200 hover:border-orange-300'
                  }`}
                >
                  <DocumentArrowUpIcon className="h-8 w-8 text-orange-500 mb-3" />
                  <h4 className="text-lg font-semibold text-gray-900 mb-2">From File</h4>
                  <p className="text-gray-600 text-sm">
                    Upload CSV or Excel files exported from ServiceNow
                  </p>
                  <ul className="mt-3 text-sm text-gray-600 space-y-1">
                    <li>• Support for CSV and Excel formats</li>
                    <li>• Process tickets, incidents, knowledge articles</li>
                    <li>• Offline processing</li>
                  </ul>
                </button>

                <button
                  onClick={() => setSelectedMethod('connection')}
                  className={`p-6 border-2 rounded-lg text-left transition-all ${
                    selectedMethod === 'connection'
                      ? 'border-orange-500 bg-orange-50'
                      : 'border-gray-200 hover:border-orange-300'
                  }`}
                >
                  <CloudIcon className="h-8 w-8 text-orange-500 mb-3" />
                  <h4 className="text-lg font-semibold text-gray-900 mb-2">Direct Connection</h4>
                  <p className="text-gray-600 text-sm">
                    Connect directly to ServiceNow instance via API
                  </p>
                  <ul className="mt-3 text-sm text-gray-600 space-y-1">
                    <li>• Real-time data synchronization</li>
                    <li>• Custom queries and filters</li>
                    <li>• Live data processing</li>
                  </ul>
                </button>
              </div>
            </div>

            {/* File Upload Section */}
            {selectedMethod === 'file' && (
              <div className="border border-gray-200 rounded-lg p-6">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">Upload ServiceNow Files</h4>
                <div className="space-y-4">
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                    <DocumentArrowUpIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <input
                      type="file"
                      multiple
                      accept=".csv,.xlsx,.xls"
                      onChange={handleFileUpload}
                      className="hidden"
                      id="servicenow-file-upload"
                    />
                    <label
                      htmlFor="servicenow-file-upload"
                      className="cursor-pointer bg-orange-500 text-white px-6 py-2 rounded-lg hover:bg-orange-600 transition-colors"
                    >
                      Choose Files
                    </label>
                    <p className="text-gray-500 text-sm mt-2">
                      CSV or Excel files exported from ServiceNow
                    </p>
                  </div>

                  {uploadedFiles.length > 0 && (
                    <div className="space-y-2">
                      <h5 className="font-medium text-gray-900">Selected Files:</h5>
                      {uploadedFiles.map((file, index) => (
                        <div key={index} className="flex items-center justify-between bg-gray-50 p-3 rounded">
                          <span className="text-sm text-gray-700">{file.name}</span>
                          <span className="text-xs text-gray-500">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Direct Connection Section */}
            {selectedMethod === 'connection' && (
              <div className="border border-gray-200 rounded-lg p-6">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">ServiceNow Connection Details</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Instance URL *
                    </label>
                    <input
                      type="url"
                      value={connectionData.instanceUrl}
                      onChange={(e) => handleConnectionChange('instanceUrl', e.target.value)}
                      placeholder="https://your-instance.service-now.com"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Table Name *
                    </label>
                    <input
                      type="text"
                      value={connectionData.tableName}
                      onChange={(e) => handleConnectionChange('tableName', e.target.value)}
                      placeholder="incident, problem, change_request"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Username *
                    </label>
                    <input
                      type="text"
                      value={connectionData.username}
                      onChange={(e) => handleConnectionChange('username', e.target.value)}
                      placeholder="your-username"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Password *
                    </label>
                    <input
                      type="password"
                      value={connectionData.password}
                      onChange={(e) => handleConnectionChange('password', e.target.value)}
                      placeholder="your-password"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Custom Query (Optional)
                  </label>
                  <textarea
                    value={connectionData.query}
                    onChange={(e) => handleConnectionChange('query', e.target.value)}
                    placeholder="sysparm_query=active=true^priority=1"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Use ServiceNow query syntax to filter data
                  </p>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex justify-end space-x-4 pt-6 border-t border-gray-200">
              <button
                onClick={onCancel}
                className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateFabric}
                disabled={!selectedMethod || isProcessing}
                className="px-6 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center"
              >
                {isProcessing ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Creating...
                  </>
                ) : (
                  'Create Knowledge Fabric'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ServiceNowKnowledgeFabric;
