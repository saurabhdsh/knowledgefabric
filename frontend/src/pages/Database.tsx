import React, { useState } from 'react';
import {
  ServerIcon,
  CloudIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowRightIcon,
  CircleStackIcon,
  EyeIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';

interface DatabaseConnection {
  type: 'mongodb' | 'postgresql' | 'mysql' | 'sqlite';
  name: string;
  description: string;
  icon: React.ComponentType<any>;
  color: string;
  gradient: string;
}

interface MongoDBConnectionData {
  connection_string: string;
  database_name: string;
  collection_name: string;
  query?: any;
  limit?: number;
  projection?: any;
}

const Database: React.FC = () => {
  const [selectedConnection, setSelectedConnection] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [connectionMessage, setConnectionMessage] = useState('');
  const [showMongoForm, setShowMongoForm] = useState(false);
  const [mongodbData, setMongodbData] = useState<MongoDBConnectionData>({
    connection_string: '',
    database_name: '',
    collection_name: '',
    limit: 1000
  });
  const [collections, setCollections] = useState<any[]>([]);
  const [previewData, setPreviewData] = useState<any>(null);

  const databaseConnections: DatabaseConnection[] = [
    {
      type: 'mongodb',
      name: 'MongoDB Atlas',
      description: 'Connect to MongoDB Atlas cloud database',
      icon: CloudIcon,
      color: 'green',
      gradient: 'from-green-500 to-green-600'
    },
    {
      type: 'postgresql',
      name: 'PostgreSQL',
      description: 'Connect to PostgreSQL database',
      icon: CircleStackIcon,
      color: 'blue',
      gradient: 'from-blue-500 to-blue-600'
    },
    {
      type: 'mysql',
      name: 'MySQL',
      description: 'Connect to MySQL database',
      icon: ServerIcon,
      color: 'orange',
      gradient: 'from-orange-500 to-orange-600'
    },
    {
      type: 'sqlite',
      name: 'SQLite',
      description: 'Connect to SQLite database file',
      icon: CircleStackIcon,
      color: 'purple',
      gradient: 'from-purple-500 to-purple-600'
    }
  ];

  const handleConnectionSelect = (connectionType: string) => {
    setSelectedConnection(connectionType);
    setConnectionStatus('idle');
    setConnectionMessage('');
    
    if (connectionType === 'mongodb') {
      setShowMongoForm(true);
    } else {
      setShowMongoForm(false);
    }
  };

  const handleMongoDBTest = async () => {
    if (!mongodbData.connection_string || !mongodbData.database_name || !mongodbData.collection_name) {
      setConnectionStatus('error');
      setConnectionMessage('Please fill in connection string, database name, and collection name');
      return;
    }

    setIsConnecting(true);
    setConnectionStatus('testing');
    setConnectionMessage('Testing MongoDB Atlas connection...');

    try {
      const response = await apiRequest('api/v1/database/mongodb/test-connection', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          connection_string: mongodbData.connection_string,
          database_name: mongodbData.database_name,
          collection_name: mongodbData.collection_name
        }),
      });

      const result = await response.json();

      if (result.success) {
        setConnectionStatus('success');
        setConnectionMessage(`Connection successful! Found ${result.data.document_count} documents in ${result.data.collection_name}`);
      } else {
        setConnectionStatus('error');
        setConnectionMessage(result.message || 'Connection failed');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionMessage('Failed to connect to MongoDB Atlas');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleMongoDBConnect = async () => {
    if (!mongodbData.connection_string || !mongodbData.database_name || !mongodbData.collection_name) {
      setConnectionStatus('error');
      setConnectionMessage('Please fill in all required fields');
      return;
    }

    setIsConnecting(true);
    setConnectionStatus('testing');
    setConnectionMessage('Connecting to MongoDB Atlas and importing data...');

    try {
      const response = await apiRequest('api/v1/database/mongodb/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(mongodbData),
      });

      const result = await response.json();

      if (result.success) {
        setConnectionStatus('success');
        setConnectionMessage(`Successfully imported ${result.data.documents_processed} documents from ${result.data.connection_info.database}.${result.data.connection_info.collection}`);
        
        // Reset form
        setMongodbData({
          connection_string: '',
          database_name: '',
          collection_name: '',
          limit: 1000
        });
        setSelectedConnection(null);
        setShowMongoForm(false);
      } else {
        setConnectionStatus('error');
        setConnectionMessage(result.message || 'Connection failed');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionMessage('Failed to connect to MongoDB Atlas');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleGetCollections = async () => {
    if (!mongodbData.connection_string || !mongodbData.database_name) {
      setConnectionMessage('Please fill in connection string and database name first');
      return;
    }

    try {
      const response = await apiRequest('api/v1/database/mongodb/collections', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(mongodbData),
      });

      const result = await response.json();

      if (result.success) {
        setCollections(result.data.collections);
        setConnectionMessage(`Found ${result.data.total_collections} collections`);
      } else {
        setConnectionMessage(result.message || 'Failed to get collections');
      }
    } catch (error) {
      setConnectionMessage('Failed to get collections');
    }
  };

  const handlePreviewData = async () => {
    if (!mongodbData.connection_string || !mongodbData.database_name || !mongodbData.collection_name) {
      setConnectionMessage('Please fill in all required fields first');
      return;
    }

    try {
      const response = await apiRequest('api/v1/database/mongodb/preview', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(mongodbData),
      });

      const result = await response.json();

      if (result.success) {
        setPreviewData(result.data);
        setConnectionMessage(`Preview generated with ${result.data.preview_count} sample documents`);
      } else {
        setConnectionMessage(result.message || 'Failed to preview data');
      }
    } catch (error) {
      setConnectionMessage('Failed to preview data');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex items-center justify-center mb-4">
          <div className="p-3 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full">
            <CircleStackIcon className="h-8 w-8 text-white" />
          </div>
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Database Connections
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          Connect to external databases and import data into your knowledge fabric
        </p>
      </div>

      {/* Database Options Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        {databaseConnections.map((connection) => (
          <div
            key={connection.type}
            className={`relative group cursor-pointer transition-all duration-300 transform hover:scale-105 ${
              selectedConnection === connection.type
                ? 'ring-4 ring-indigo-500 ring-opacity-50'
                : 'hover:shadow-2xl'
            }`}
            onClick={() => handleConnectionSelect(connection.type)}
          >
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 h-full">
              {/* Icon */}
              <div className={`w-12 h-12 bg-gradient-to-r ${connection.gradient} rounded-xl flex items-center justify-center mb-4`}>
                <connection.icon className="h-6 w-6 text-white" />
              </div>

              {/* Content */}
              <h3 className="text-lg font-bold text-gray-900 mb-2">
                {connection.name}
              </h3>
              <p className="text-sm text-gray-600">
                {connection.description}
              </p>

              {/* Selection Indicator */}
              {selectedConnection === connection.type && (
                <div className="absolute top-4 right-4">
                  <div className="w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center">
                    <CheckCircleIcon className="h-4 w-4 text-white" />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* MongoDB Atlas Connection Form */}
      {showMongoForm && (
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">MongoDB Atlas Connection</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Connection String *
              </label>
              <input
                type="text"
                value={mongodbData.connection_string}
                onChange={(e) => setMongodbData({...mongodbData, connection_string: e.target.value})}
                placeholder="mongodb+srv://username:password@cluster.mongodb.net/"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Database Name *
              </label>
              <input
                type="text"
                value={mongodbData.database_name}
                onChange={(e) => setMongodbData({...mongodbData, database_name: e.target.value})}
                placeholder="my_database"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Collection Name *
              </label>
              <input
                type="text"
                value={mongodbData.collection_name}
                onChange={(e) => setMongodbData({...mongodbData, collection_name: e.target.value})}
                placeholder="my_collection"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Document Limit
              </label>
              <input
                type="number"
                value={mongodbData.limit}
                onChange={(e) => setMongodbData({...mongodbData, limit: parseInt(e.target.value) || 1000})}
                placeholder="1000"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-4 mt-6">
            <button
              onClick={handleMongoDBTest}
              disabled={isConnecting}
              className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
            >
              <PlayIcon className="h-5 w-5" />
              <span>Test Connection</span>
            </button>
            
            <button
              onClick={handleGetCollections}
              disabled={isConnecting}
              className="px-6 py-3 bg-gray-600 text-white font-semibold rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center space-x-2"
            >
              <CircleStackIcon className="h-5 w-5" />
              <span>Get Collections</span>
            </button>
            
            <button
              onClick={handlePreviewData}
              disabled={isConnecting}
              className="px-6 py-3 bg-purple-600 text-white font-semibold rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center space-x-2"
            >
              <EyeIcon className="h-5 w-5" />
              <span>Preview Data</span>
            </button>
            
            <button
              onClick={handleMongoDBConnect}
              disabled={isConnecting || connectionStatus !== 'success'}
              className="px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center space-x-2"
            >
              <ArrowRightIcon className="h-5 w-5" />
              <span>Connect & Import</span>
            </button>
          </div>

          {/* Connection Status */}
          {connectionMessage && (
            <div className={`mt-6 p-4 rounded-lg flex items-center space-x-3 ${
              connectionStatus === 'success' ? 'bg-green-50 text-green-800' :
              connectionStatus === 'error' ? 'bg-red-50 text-red-800' :
              connectionStatus === 'testing' ? 'bg-blue-50 text-blue-800' :
              'bg-gray-50 text-gray-800'
            }`}>
              {connectionStatus === 'success' && <CheckCircleIcon className="h-5 w-5 text-green-600" />}
              {connectionStatus === 'error' && <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />}
              {connectionStatus === 'testing' && (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
              )}
              <span className="text-sm font-medium">{connectionMessage}</span>
            </div>
          )}

          {/* Collections List */}
          {collections.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Available Collections</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {collections.map((collection, index) => (
                  <div key={index} className="bg-gray-50 rounded-lg p-3">
                    <div className="font-medium text-gray-900">{collection.name}</div>
                    <div className="text-sm text-gray-600">{collection.document_count} documents</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Preview Data */}
          {previewData && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Data Preview</h3>
              <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
                <div className="text-sm text-gray-600 mb-2">
                  Showing {previewData.preview_count} of {previewData.total_documents} documents
                </div>
                <pre className="text-xs text-gray-800 whitespace-pre-wrap">
                  {JSON.stringify(previewData.sample_documents, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Other Database Types Placeholder */}
      {selectedConnection && selectedConnection !== 'mongodb' && (
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            {databaseConnections.find(db => db.type === selectedConnection)?.name} Connection
          </h2>
          <p className="text-gray-600">
            {databaseConnections.find(db => db.type === selectedConnection)?.name} connection form will be implemented here.
          </p>
        </div>
      )}

      {/* Info Section */}
      <div className="mt-12 bg-white rounded-2xl shadow-lg p-8 border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <CloudIcon className="h-6 w-6 text-blue-600" />
            </div>
            <h4 className="font-semibold text-gray-900 mb-2">MongoDB Atlas Support</h4>
            <p className="text-sm text-gray-600">
              Connect directly to MongoDB Atlas cloud databases with secure connection strings
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <CircleStackIcon className="h-6 w-6 text-green-600" />
            </div>
            <h4 className="font-semibold text-gray-900 mb-2">Multiple Database Types</h4>
            <p className="text-sm text-gray-600">
              Support for PostgreSQL, MySQL, SQLite, and MongoDB Atlas connections
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <ArrowRightIcon className="h-6 w-6 text-purple-600" />
            </div>
            <h4 className="font-semibold text-gray-900 mb-2">Knowledge Fabric Integration</h4>
            <p className="text-sm text-gray-600">
              Automatically process and import data into your knowledge fabric for AI agents
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Database; 