import React, { useEffect, useState } from 'react';
import {
  CloudIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowRightIcon,
  CircleStackIcon,
  PlayIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';
import FabricCreationProgressModal, {
  FabricProgressStep,
} from './FabricCreationProgressModal';

/** FastAPI returns errors in `detail` (string or validation array); APIResponse uses `message`. */
function formatKnowledgeApiError(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) {
    return d.detail
      .map((item: unknown) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg?: string }).msg ?? '');
        }
        return typeof item === 'string' ? item : JSON.stringify(item);
      })
      .filter(Boolean)
      .join(' ');
  }
  if (typeof d.message === 'string') return d.message;
  return fallback;
}

interface MongoDBConnectionData {
  connection_string: string;
  database_name: string;
  collection_name: string;
  query?: any;
  limit?: number;
  projection?: any;
}

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

interface DatabaseKnowledgeFabricProps {
  onComplete: (fabricId: string) => void;
  onCancel: () => void;
  weaveDomain?: 'generic' | 'pharma';
  connectorProfile?: string | null;
  guardrails?: FabricGuardrails;
}

function buildDbProgressSteps(inputMode: 'live' | 'csv', trainModel: boolean): FabricProgressStep[] {
  return [
    {
      id: 'fetch',
      title: inputMode === 'csv' ? 'Reading CSV datasets' : 'Fetching source records',
      description:
        inputMode === 'csv'
          ? 'Loading row batches and validating schema consistency'
          : 'Pulling records from your selected database connection',
      status: 'pending',
      progress: 0,
    },
    {
      id: 'normalize',
      title: 'Normalizing tabular context',
      description: 'Converting rows into semantic chunks and metadata',
      status: 'pending',
      progress: 0,
    },
    {
      id: 'embed',
      title: 'Generating embeddings',
      description: 'Vectorizing tabular content for semantic retrieval',
      status: 'pending',
      progress: 0,
    },
    {
      id: 'store',
      title: 'Storing in vector database',
      description: 'Persisting vectors and source lineage in ChromaDB',
      status: 'pending',
      progress: 0,
    },
    {
      id: 'finalize',
      title: trainModel ? 'Training retrieval profile' : 'Finalizing knowledge fabric',
      description: trainModel
        ? 'Optimizing retrieval and ranking signals for this dataset'
        : 'Finishing index metadata and activation',
      status: 'pending',
      progress: 0,
    },
  ];
}

const DB_PROGRESS_STEP_DURATIONS_MS = [1300, 1200, 1700, 1400];

const DatabaseKnowledgeFabric: React.FC<DatabaseKnowledgeFabricProps> = ({
  onComplete,
  onCancel,
  weaveDomain = 'generic',
  connectorProfile,
  guardrails,
}) => {
  const [connectionType, setConnectionType] = useState<'mongodb' | 'databricks' | 'snowflake' | 'postgresql' | 'mysql' | 'sqlite'>('mongodb');
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [connectionMessage, setConnectionMessage] = useState('');
  const [mongodbData, setMongodbData] = useState<MongoDBConnectionData>({
    connection_string: '',
    database_name: '',
    collection_name: '',
    limit: 1000
  });
  const [databricksData, setDatabricksData] = useState({
    server_hostname: '',
    warehouse_id: '',
    access_token: '',
    catalog: 'workspace',
    schema: 'default',
    table_name: '',
    query: '',
    limit: 1000
  });
  const [snowflakeData, setSnowflakeData] = useState({
    account: '',
    user: '',
    password: '',
    warehouse: '',
    database: '',
    schema: 'PUBLIC',
    role: '',
    table_name: '',
    query: '',
    limit: 1000
  });
  const [trainModel, setTrainModel] = useState(true);
  const [inputMode, setInputMode] = useState<'live' | 'csv'>('live');
  const [csvFiles, setCsvFiles] = useState<File[]>([]);
  const [csvDatasetLabel, setCsvDatasetLabel] = useState('');
  const [showCreationProgress, setShowCreationProgress] = useState(false);
  const [creationProgressSteps, setCreationProgressSteps] = useState<FabricProgressStep[]>([]);
  const [creationOverallProgress, setCreationOverallProgress] = useState(0);

  useEffect(() => {
    setConnectionStatus('idle');
    setConnectionMessage('');
  }, [inputMode, connectionType]);

  const isBlank = (value: unknown): boolean =>
    typeof value !== 'string' || value.trim().length === 0;

  const getCurrentConnectionPayload = () => {
    if (connectionType === 'mongodb') {
      return {
        ...mongodbData,
        connection_string: mongodbData.connection_string.trim(),
        database_name: mongodbData.database_name.trim(),
        collection_name: mongodbData.collection_name.trim(),
      };
    }
    if (connectionType === 'databricks') {
      return {
        ...databricksData,
        server_hostname: databricksData.server_hostname
          .replace(/^https?:\/\//i, '')
          .replace(/\/+$/, '')
          .trim(),
        warehouse_id: databricksData.warehouse_id.trim(),
        access_token: databricksData.access_token.trim(),
        catalog: databricksData.catalog.trim() || 'workspace',
        schema: databricksData.schema.trim() || 'default',
        table_name: databricksData.table_name.trim(),
        query: databricksData.query.trim(),
      };
    }
    if (connectionType === 'snowflake') {
      return {
        ...snowflakeData,
        account: snowflakeData.account.trim(),
        user: snowflakeData.user.trim(),
        password: snowflakeData.password,
        warehouse: snowflakeData.warehouse.trim(),
        database: snowflakeData.database.trim(),
        schema: snowflakeData.schema.trim(),
        role: snowflakeData.role.trim(),
        table_name: snowflakeData.table_name.trim(),
        query: snowflakeData.query.trim(),
      };
    }
    return {};
  };

  const validateRequiredFields = (): string | null => {
    if (inputMode === 'csv') {
      if (csvFiles.length === 0) return 'Please choose at least one CSV file.';
      return null;
    }
    if (connectionType === 'mongodb') {
      const missing: string[] = [];
      if (isBlank(mongodbData.connection_string)) missing.push('Connection String');
      if (isBlank(mongodbData.database_name)) missing.push('Database Name');
      if (isBlank(mongodbData.collection_name)) missing.push('Collection Name');
      if (missing.length > 0) return `Please fill in: ${missing.join(', ')}.`;
      return null;
    }
    if (connectionType === 'databricks') {
      const missing: string[] = [];
      if (isBlank(databricksData.server_hostname)) missing.push('Workspace URL');
      if (isBlank(databricksData.warehouse_id)) missing.push('Warehouse ID');
      if (isBlank(databricksData.access_token)) missing.push('Access Token');
      if (isBlank(databricksData.table_name) && isBlank(databricksData.query)) {
        missing.push('Table Name (or Custom SQL)');
      }
      if (missing.length > 0) return `Please fill in: ${missing.join(', ')}.`;
      return null;
    }
    if (connectionType === 'snowflake') {
      const missing: string[] = [];
      if (isBlank(snowflakeData.account)) missing.push('Account');
      if (isBlank(snowflakeData.user)) missing.push('User');
      if (isBlank(snowflakeData.password)) missing.push('Password');
      if (isBlank(snowflakeData.warehouse)) missing.push('Warehouse');
      if (isBlank(snowflakeData.database)) missing.push('Database');
      if (isBlank(snowflakeData.schema)) missing.push('Schema');
      if (isBlank(snowflakeData.table_name)) missing.push('Table Name');
      if (missing.length > 0) return `Please fill in: ${missing.join(', ')}.`;
      return null;
    }
    return 'Selected database type is not yet supported for live connection.';
  };

  const handleTestConnection = async () => {
    const validationError = validateRequiredFields();
    if (validationError) {
      setConnectionStatus('error');
      setConnectionMessage(validationError);
      return;
    }

    setIsConnecting(true);
    setConnectionStatus('testing');

    if (inputMode === 'csv') {
      setConnectionMessage('Validating CSV file(s)...');
      try {
        const formData = new FormData();
        csvFiles.forEach((f) => formData.append('files', f));
        const response = await apiRequest('api/v1/knowledge/preview-database-csv', {
          method: 'POST',
          body: formData,
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          setConnectionStatus('error');
          setConnectionMessage(formatKnowledgeApiError(result, `CSV validation failed (${response.status})`));
          return;
        }
        if (result.success) {
          setConnectionStatus('success');
          const cols = result.data?.columns?.length ?? 0;
          setConnectionMessage(
            `CSV OK — ${result.data?.total_rows ?? 0} row(s), ${cols} column(s). Profile: ${connectionType}. Ready to create fabric.`
          );
        } else {
          setConnectionStatus('error');
          setConnectionMessage(
            formatKnowledgeApiError(result, typeof result.message === 'string' ? result.message : 'CSV validation failed')
          );
        }
      } catch (err) {
        setConnectionStatus('error');
        setConnectionMessage(err instanceof Error ? err.message : 'Failed to validate CSV file(s)');
      } finally {
        setIsConnecting(false);
      }
      return;
    }

    setConnectionMessage(`Testing ${connectionType} connection...`);

    try {
      const response = await apiRequest('api/v1/knowledge/test-database-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_type: connectionType,
          connection_data: getCurrentConnectionPayload()
        }),
      });
      const result = await response.json();
      if (result.success) {
        setConnectionStatus('success');
        setConnectionMessage(`Connection successful! Rows available: ${result.data?.rows_found ?? 0}`);
      } else {
        setConnectionStatus('error');
        setConnectionMessage(result.message || 'Connection test failed');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionMessage(`Failed to test ${connectionType} connection`);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleCreateFabric = async () => {
    const validationError = validateRequiredFields();
    if (validationError) {
      setConnectionStatus('error');
      setConnectionMessage(validationError);
      return;
    }

    setIsConnecting(true);
    setConnectionStatus('testing');

    const progressSteps = buildDbProgressSteps(inputMode, trainModel);
    const totalSteps = progressSteps.length;
    setCreationProgressSteps(progressSteps);
    setCreationOverallProgress(0);
    setShowCreationProgress(true);

    const updateProgressStepStatus = (stepIndex: number, status: FabricProgressStep['status']) => {
      setCreationProgressSteps((prev) =>
        prev.map((step, index) => (index === stepIndex ? { ...step, status } : step))
      );
    };

    const animateStep = (stepIndex: number, duration: number, target = 100) =>
      new Promise<void>((resolve) => {
        const started = performance.now();
        const tick = (time: number) => {
          const elapsed = time - started;
          const pct = Math.min((elapsed / duration) * target, target);
          setCreationProgressSteps((prev) =>
            prev.map((step, index) => (index === stepIndex ? { ...step, progress: pct } : step))
          );
          setCreationOverallProgress(((stepIndex + pct / 100) / totalSteps) * 100);
          if (pct < target) {
            requestAnimationFrame(tick);
            return;
          }
          resolve();
        };
        requestAnimationFrame(tick);
      });

    const runCreationProgressAndComplete = async (createFabricRequest: () => Promise<string>) => {
      try {
        const creationPromise = createFabricRequest();

        for (let i = 0; i < totalSteps - 1; i += 1) {
          updateProgressStepStatus(i, 'processing');
          await animateStep(i, DB_PROGRESS_STEP_DURATIONS_MS[i] ?? 1200, 100);
          updateProgressStepStatus(i, 'completed');
        }

        const finalStep = totalSteps - 1;
        updateProgressStepStatus(finalStep, 'processing');
        await animateStep(finalStep, 1400, 85);

        const fabricId = await creationPromise;
        await animateStep(finalStep, 300, 100);
        updateProgressStepStatus(finalStep, 'completed');
        setCreationOverallProgress(100);

        setConnectionStatus('success');
        setConnectionMessage(`Knowledge fabric created successfully! Fabric ID: ${fabricId}`);
        setTimeout(() => {
          setShowCreationProgress(false);
          onComplete(fabricId);
        }, 900);
      } catch (err) {
        setShowCreationProgress(false);
        setConnectionStatus('error');
        setConnectionMessage(
          err instanceof Error ? err.message : 'Failed to create knowledge fabric'
        );
      } finally {
        setIsConnecting(false);
      }
    };

    if (inputMode === 'csv') {
      setConnectionMessage(`Creating knowledge fabric from CSV (${connectionType} profile)...`);
      await runCreationProgressAndComplete(async () => {
        const formData = new FormData();
        csvFiles.forEach((f) => formData.append('files', f));
        formData.append('connection_type', connectionType);
        formData.append('dataset_label', csvDatasetLabel);
        formData.append('train_model', trainModel ? 'true' : 'false');
        formData.append('weave_domain', weaveDomain);
        if (connectorProfile) formData.append('connector_profile', connectorProfile);
        if (guardrails) formData.append('guardrails', JSON.stringify(guardrails));

        const response = await apiRequest('api/v1/knowledge/create-database-fabric-csv', {
          method: 'POST',
          body: formData,
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(
            formatKnowledgeApiError(result, `Failed to create fabric (${response.status})`)
          );
        }
        if (!result.success) {
          throw new Error(
            formatKnowledgeApiError(
              result,
              typeof result.message === 'string'
                ? result.message
                : 'Failed to create knowledge fabric'
            )
          );
        }
        return result.data.source_id;
      });
      return;
    }

    setConnectionMessage(`Creating knowledge fabric from ${connectionType} data...`);
    await runCreationProgressAndComplete(async () => {
      const response = await apiRequest('api/v1/knowledge/create-database-fabric', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_type: connectionType,
          connection_data: getCurrentConnectionPayload(),
          train_model: trainModel,
          weave_domain: weaveDomain,
          ...(connectorProfile ? { connector_profile: connectorProfile } : {}),
          ...(guardrails ? { guardrails } : {}),
        }),
      });
      const result = await response.json();
      if (!result.success) {
        throw new Error(result.message || 'Failed to create knowledge fabric');
      }
      return result.data.source_id;
    });
  };

  const showActions =
    inputMode === 'csv' ||
    (inputMode === 'live' && (connectionType === 'mongodb' || connectionType === 'databricks' || connectionType === 'snowflake'));

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50">
      <div className="bg-[#10141d]/92 rounded-2xl p-8 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-[rgba(148,163,184,0.2)] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_textarea]:bg-[#10141d]/70 [&_textarea]:text-[#e8edf4] [&_textarea]:border-[rgba(148,163,184,0.2)] [&_textarea]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-r from-green-500 to-green-600 rounded-lg">
              <CircleStackIcon className="h-6 w-6 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900">Create Knowledge Fabric from Database</h2>
          </div>
          <button
            onClick={onCancel}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-6 w-6 text-gray-500" />
          </button>
        </div>

        {/* Connection Type Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Database Type
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { type: 'mongodb', name: 'MongoDB Atlas', icon: CloudIcon },
              { type: 'databricks', name: 'Databricks', icon: CircleStackIcon },
              { type: 'snowflake', name: 'Snowflake', icon: CloudIcon },
              { type: 'postgresql', name: 'PostgreSQL', icon: CircleStackIcon },
            ].map((db) => (
              <button
                key={db.type}
                onClick={() => setConnectionType(db.type as any)}
                className={`p-3 rounded-xl border transition-all duration-200 backdrop-blur-sm ${
                  connectionType === db.type
                    ? 'border-[rgba(94,200,242,0.45)] bg-[rgba(94,200,242,0.12)] shadow-[0_0_0_1px_rgba(94,200,242,0.2)]'
                    : 'border-[rgba(148,163,184,0.2)] bg-white/[0.03] hover:border-[rgba(148,163,184,0.35)] hover:bg-white/[0.05]'
                }`}
              >
                <db.icon className={`h-5 w-5 mx-auto mb-2 ${connectionType === db.type ? 'text-[#5ec8f2]' : 'text-[#8b9cb0]'}`} />
                <div className={`text-sm font-medium ${connectionType === db.type ? 'text-[#e8edf4]' : 'text-[#cbd5e1]'}`}>{db.name}</div>
                <div className={`mt-1 text-[10px] uppercase tracking-[0.16em] ${connectionType === db.type ? 'text-[#5ec8f2]' : 'text-[#8b9cb0]'}`}>
                  {connectionType === db.type ? 'Selected' : 'Available'}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Live connection vs CSV export */}
        <div className="mb-6 rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-4">
          <label className="block text-sm font-medium text-[#cbd5e1] mb-3">Data source</label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setInputMode('live')}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                inputMode === 'live'
                  ? 'bg-[rgba(94,200,242,0.2)] text-[#e8edf4] border border-[rgba(94,200,242,0.4)]'
                  : 'border border-[rgba(148,163,184,0.2)] text-[#8b9cb0] hover:text-[#cbd5e1]'
              }`}
            >
              Live database connection
            </button>
            <button
              type="button"
              onClick={() => setInputMode('csv')}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                inputMode === 'csv'
                  ? 'bg-[rgba(62,207,155,0.18)] text-[#e8edf4] border border-[rgba(62,207,155,0.35)]'
                  : 'border border-[rgba(148,163,184,0.2)] text-[#8b9cb0] hover:text-[#cbd5e1]'
              }`}
            >
              Upload CSV export
            </button>
          </div>
          <p className="mt-2 text-xs text-[#8b9cb0]">
            CSV uses the same fabric pipeline as live database pulls. Pick the database type above so exports are tagged correctly (MongoDB, Databricks, Snowflake, PostgreSQL, etc.).
          </p>
        </div>

        {inputMode === 'csv' && (
          <div className="mb-6 rounded-xl border border-[rgba(62,207,155,0.28)] bg-[rgba(62,207,155,0.06)] p-4 space-y-3">
            <h3 className="text-sm font-semibold text-[#e8edf4]">CSV file(s)</h3>
            <p className="text-xs text-[#8b9cb0]">
              Upload one or more comma-separated files (.csv). Multiple files are combined into one fabric. Tagged as:{' '}
              <span className="text-[#3ecf9b] font-medium">{connectionType}</span>
            </p>
            <label className="flex flex-col items-center justify-center w-full py-4 px-3 rounded-lg border-2 border-dashed border-[rgba(62,207,155,0.35)] cursor-pointer hover:bg-[rgba(62,207,155,0.08)]">
              <span className="text-sm text-[#cbd5e1]">Choose .csv files</span>
              <input
                type="file"
                accept=".csv,text/csv"
                multiple
                className="hidden"
                onChange={(e) => setCsvFiles(Array.from(e.target.files || []))}
              />
            </label>
            {csvFiles.length > 0 && (
              <ul className="text-xs text-[#cbd5e1] space-y-1 max-h-28 overflow-y-auto">
                {csvFiles.map((f) => (
                  <li key={`${f.name}-${f.size}`}>{f.name}</li>
                ))}
              </ul>
            )}
            <div>
              <label className="block text-xs font-medium text-[#8b9cb0] mb-1">Dataset label (optional)</label>
              <input
                type="text"
                value={csvDatasetLabel}
                onChange={(e) => setCsvDatasetLabel(e.target.value)}
                placeholder="e.g. production_batches_export"
                className="w-full px-3 py-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#10141d]/70 text-[#e8edf4] text-sm"
              />
            </div>
          </div>
        )}

        {/* MongoDB Atlas Connection Form */}
        {connectionType === 'mongodb' && inputMode === 'live' && (
          <div className="space-y-6">
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
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
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
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
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
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
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
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                />
              </div>
            </div>
          </div>
        )}

        {connectionType === 'databricks' && inputMode === 'live' && (
          <div className="space-y-6">
            <p className="text-xs text-[#8b9cb0]">
              Uses the Databricks <span className="text-[#cbd5e1] font-mono">/api/2.0/sql/statements/</span> REST API with a Bearer access token and SQL Warehouse.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Workspace URL *</label>
                <input
                  type="text"
                  value={databricksData.server_hostname}
                  onChange={(e) => setDatabricksData({ ...databricksData, server_hostname: e.target.value })}
                  placeholder="dbc-xxxx.cloud.databricks.com"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
                <p className="mt-1 text-[11px] text-[#8b9cb0]">Host only — the <span className="font-mono">https://</span> prefix is optional.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Warehouse ID *</label>
                <input
                  type="text"
                  value={databricksData.warehouse_id}
                  onChange={(e) => setDatabricksData({ ...databricksData, warehouse_id: e.target.value })}
                  placeholder="e.g. 1234567890abcdef"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
                <p className="mt-1 text-[11px] text-[#8b9cb0]">SQL Warehouse ID (the <span className="font-mono">warehouse_id</span> in the REST API body).</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Access Token *</label>
                <input
                  type="password"
                  value={databricksData.access_token}
                  onChange={(e) => setDatabricksData({ ...databricksData, access_token: e.target.value })}
                  placeholder="dapi..."
                  autoComplete="off"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
                <p className="mt-1 text-[11px] text-[#8b9cb0]">Bearer token sent in the <span className="font-mono">Authorization</span> header.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Table Name *</label>
                <input
                  type="text"
                  value={databricksData.table_name}
                  onChange={(e) => setDatabricksData({ ...databricksData, table_name: e.target.value })}
                  placeholder="csnp_members_tables"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Catalog</label>
                <input
                  type="text"
                  value={databricksData.catalog}
                  onChange={(e) => setDatabricksData({ ...databricksData, catalog: e.target.value })}
                  placeholder="workspace"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Schema</label>
                <input
                  type="text"
                  value={databricksData.schema}
                  onChange={(e) => setDatabricksData({ ...databricksData, schema: e.target.value })}
                  placeholder="default"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Row Limit</label>
                <input
                  type="number"
                  value={databricksData.limit}
                  onChange={(e) => setDatabricksData({ ...databricksData, limit: parseInt(e.target.value) || 1000 })}
                  placeholder="1000"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                />
                <p className="mt-1 text-[11px] text-[#8b9cb0]">Used when no Custom SQL is provided.</p>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Custom SQL (optional — overrides Catalog/Schema/Table)</label>
              <textarea
                rows={3}
                value={databricksData.query}
                onChange={(e) => setDatabricksData({ ...databricksData, query: e.target.value })}
                placeholder="SELECT * FROM workspace.default.csnp_members_tables LIMIT 10"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg font-mono text-sm"
              />
            </div>
          </div>
        )}

        {connectionType === 'snowflake' && inputMode === 'live' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Account *</label><input type="text" value={snowflakeData.account} onChange={(e) => setSnowflakeData({ ...snowflakeData, account: e.target.value })} placeholder="xy12345.us-east-1" className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">User *</label><input type="text" value={snowflakeData.user} onChange={(e) => setSnowflakeData({ ...snowflakeData, user: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Password *</label><input type="password" value={snowflakeData.password} onChange={(e) => setSnowflakeData({ ...snowflakeData, password: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Warehouse *</label><input type="text" value={snowflakeData.warehouse} onChange={(e) => setSnowflakeData({ ...snowflakeData, warehouse: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Database *</label><input type="text" value={snowflakeData.database} onChange={(e) => setSnowflakeData({ ...snowflakeData, database: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Schema *</label><input type="text" value={snowflakeData.schema} onChange={(e) => setSnowflakeData({ ...snowflakeData, schema: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Role (optional)</label><input type="text" value={snowflakeData.role} onChange={(e) => setSnowflakeData({ ...snowflakeData, role: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-2">Table Name *</label><input type="text" value={snowflakeData.table_name} onChange={(e) => setSnowflakeData({ ...snowflakeData, table_name: e.target.value })} className="w-full px-4 py-3 border border-gray-300 rounded-lg" /></div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Custom Query (optional)</label>
              <textarea rows={3} value={snowflakeData.query} onChange={(e) => setSnowflakeData({ ...snowflakeData, query: e.target.value })} placeholder="SELECT * FROM DB.SCHEMA.TABLE LIMIT 500" className="w-full px-4 py-3 border border-gray-300 rounded-lg" />
            </div>
          </div>
        )}

        {/* Other Database Types Placeholder (live only — CSV still works for these profiles) */}
        {connectionType !== 'mongodb' && connectionType !== 'databricks' && connectionType !== 'snowflake' && inputMode === 'live' && (
          <div className="text-center py-8">
            <CircleStackIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {connectionType.charAt(0).toUpperCase() + connectionType.slice(1)} live connection coming soon
            </h3>
            <p className="text-gray-600">
              Use <strong className="text-[#cbd5e1]">Upload CSV export</strong> above to ingest PostgreSQL / MySQL / SQLite dumps as CSV with that profile.
            </p>
          </div>
        )}

        {showActions && (
          <div className="space-y-4 mt-6 border-t border-[rgba(148,163,184,0.15)] pt-6">
            <div className="flex flex-wrap gap-4">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isConnecting}
                className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
              >
                <PlayIcon className="h-5 w-5" />
                <span>{inputMode === 'csv' ? 'Validate CSV' : 'Test Connection'}</span>
              </button>
              <button
                type="button"
                onClick={handleCreateFabric}
                disabled={isConnecting || connectionStatus !== 'success'}
                className="flex-1 min-w-[220px] px-8 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white font-semibold rounded-xl disabled:opacity-50 flex items-center justify-center space-x-2"
              >
                {isConnecting ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                    <span>Creating Knowledge Fabric...</span>
                  </>
                ) : (
                  <>
                    <ArrowRightIcon className="h-5 w-5" />
                    <span>Create Knowledge Fabric</span>
                  </>
                )}
              </button>
            </div>
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="trainModelDbFabric"
                checked={trainModel}
                onChange={(e) => setTrainModel(e.target.checked)}
                className="h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded"
              />
              <label htmlFor="trainModelDbFabric" className="text-sm font-medium text-gray-700">
                Train model on imported data for better AI responses
              </label>
            </div>
          </div>
        )}

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

      </div>

      <FabricCreationProgressModal
        isVisible={showCreationProgress}
        title="Creating Knowledge Fabric"
        subtitle={
          inputMode === 'csv'
            ? `Processing ${csvFiles.length} CSV file(s) with ${connectionType} profile`
            : `Ingesting records from your ${connectionType} connection`
        }
        overallProgress={creationOverallProgress}
        steps={creationProgressSteps}
      />
    </div>
  );
};

export default DatabaseKnowledgeFabric;
