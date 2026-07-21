import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  DocumentTextIcon,
  ServerIcon,
  CpuChipIcon,
  CheckCircleIcon,
  ArrowRightIcon,
  SparklesIcon,
  GlobeAltIcon,
  CloudIcon,
  Squares2X2Icon,
  BeakerIcon,
  CodeBracketSquareIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';
import {
  getWeaveDomain,
  setWeaveDomain,
  isPharmaManufacturing,
  FABRIC_KIND_OPTIONS,
  type FabricKind,
} from '../utils/weaveDomain';
import PDFUpload from '../components/PDFUpload';
import KnowledgeFabricProgress from '../components/KnowledgeFabricProgress';
import DatabaseKnowledgeFabric from '../components/DatabaseKnowledgeFabric';
import ServiceNowKnowledgeFabric from '../components/ServiceNowKnowledgeFabric';
import CodebaseKnowledgeFabric from '../components/CodebaseKnowledgeFabric';

interface KnowledgeOption {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<any>;
  features: string[];
  color: string;
  gradient: string;
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
  handbook_files: string[];
}

const Knowledge: React.FC = () => {
  const navigate = useNavigate();
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showPDFUpload, setShowPDFUpload] = useState(false);
  const [showDatabaseFabric, setShowDatabaseFabric] = useState(false);
  const [showServiceNowFabric, setShowServiceNowFabric] = useState(false);
  const [showCodebaseFabric, setShowCodebaseFabric] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [showProgress, setShowProgress] = useState(false);
  const [availableFabrics, setAvailableFabrics] = useState<any[]>([]);
  const [loadingAvailableFabrics, setLoadingAvailableFabrics] = useState(false);
  const [compositeName, setCompositeName] = useState('');
  const [compositeSourceIds, setCompositeSourceIds] = useState<string[]>([]);
  const [isCreatingComposite, setIsCreatingComposite] = useState(false);
  const [compositePendingSourceType, setCompositePendingSourceType] = useState<'pdf' | 'database' | 'servicenow' | null>(null);
  const [weaveDomain, setWeaveDomainState] = useState<FabricKind>(() => getWeaveDomain());
  const [pharmaConnector, setPharmaConnector] = useState<'pdf' | 'database' | 'servicenow' | 'composite'>('pdf');
  const [pharmaArtifacts, setPharmaArtifacts] = useState<Record<string, boolean>>({
    experiment_reports: true,
    batch_records: true,
    lab_files: false,
    lims_mes_eln: false,
    sops: true,
    protocols: true,
    analytical_tests: true,
    stability: false,
    deviation_capa: false,
    databases_tables: false,
  });
  const [guardrails, setGuardrails] = useState<FabricGuardrails>({
    data_classification: 'internal',
    compliance_tags: [],
    pii_fields: [],
    enforce_masking: true,
    encryption_at_rest: true,
    encryption_in_transit: true,
    row_level_security: false,
    approved_roles: [],
    handbook_files: [],
  });
  const [handbookUploadFiles, setHandbookUploadFiles] = useState<File[]>([]);
  const [isUploadingHandbook, setIsUploadingHandbook] = useState(false);

  useEffect(() => {
    setWeaveDomain(weaveDomain);
  }, [weaveDomain]);

  const connectorProfile = useMemo(() => {
    if (!isPharmaManufacturing(weaveDomain)) return undefined;
    const map: Record<typeof pharmaConnector, string> = {
      pdf: 'scientific_documents',
      database: 'lims_mes_eln_exports',
      servicenow: 'quality_itsm_capa',
      composite: 'multi_connector',
    };
    return map[pharmaConnector];
  }, [weaveDomain, pharmaConnector]);

  const fabricReadinessScore = useMemo(() => {
    let score = 28;
    if (isPharmaManufacturing(weaveDomain)) score += 12;
    else if (weaveDomain !== 'general') score += 10;
    if (selectedOption) score += 18;
    const toggles = Object.values(pharmaArtifacts).filter(Boolean).length;
    if (isPharmaManufacturing(weaveDomain)) score += Math.round((toggles / 10) * 38);
    else score += 15;
    return Math.min(100, score);
  }, [weaveDomain, selectedOption, pharmaArtifacts]);

  const selectedKindMeta = useMemo(
    () => FABRIC_KIND_OPTIONS.find((k) => k.id === weaveDomain) || FABRIC_KIND_OPTIONS[0],
    [weaveDomain],
  );

  const eligibleCompositeSources = useMemo(
    () => availableFabrics.filter((f) => f.source_type !== 'composite'),
    [availableFabrics]
  );

  const loadAvailableFabrics = async () => {
    setLoadingAvailableFabrics(true);
    try {
      const response = await apiRequest('api/v1/knowledge/');
      const payload = await response.json();
      if (payload.success && Array.isArray(payload.data)) {
        setAvailableFabrics(payload.data);
      }
    } catch (error) {
      console.error('Failed to load available fabrics:', error);
    } finally {
      setLoadingAvailableFabrics(false);
    }
  };

  useEffect(() => {
    loadAvailableFabrics();
  }, [showProgress, showDatabaseFabric, showServiceNowFabric, showPDFUpload, showCodebaseFabric]);

  const knowledgeOptions: KnowledgeOption[] = useMemo(() => {
    const pharmaPdfFeatures = [
      'Experiment reports, batch records, SOPs, protocols, analytical & stability PDFs',
      'Artifact type hints for auto-classification',
      'Scientific metadata extraction and evidence spans',
      'Batch / lot / product context detection',
      'Fabric readiness and staged graph outputs',
    ];
    const pharmaDbFeatures = [
      'LIMS / MES / ELN exports and analytical databases',
      'Tables mapped into scientific entities',
      'Lineage-friendly structured ingestion',
      'Same ontology-ready staging as document fabrics',
      'Secure connector testing before create',
    ];
    const pharmaSnFeatures = [
      'Deviation / CAPA / quality event feeds (CSV / API style)',
      'Links to controlled vocabularies where configured',
      'Pairs with document fabrics in composites',
      'Governance-friendly provenance metadata',
      'Incident & task exports supported',
    ];
    const pharmaCompFeatures = [
      'Unify PDF + database + ITSM fabrics for one pharma graph',
      'Cross-source evidence and lineage',
      'Recommended after at least two source fabrics exist',
      'Single composite ID for agents & ontology',
      'No duplicate re-ingestion of sources',
    ];

    return [
      {
        id: 'pdf',
        title: isPharmaManufacturing(weaveDomain) ? 'Scientific documents & reports' : 'Upload PDF Documents',
        description:
          isPharmaManufacturing(weaveDomain)
            ? 'PDF/TXT across experimental, manufacturing, and quality documentation'
            : 'Upload and process PDF files to extract knowledge and create embeddings',
        icon: DocumentTextIcon,
        features: isPharmaManufacturing(weaveDomain) ? pharmaPdfFeatures : [
          'Extract text from PDF documents',
          'Automatic chunking and processing',
          'Generate embeddings for semantic search',
          'Support for multiple PDF files',
          'Real-time processing status',
        ],
        color: 'blue',
        gradient: 'from-blue-500 to-blue-600',
      },
      {
        id: 'database',
        title: isPharmaManufacturing(weaveDomain) ? 'Databases & structured exports' : 'Connect to Database',
        description:
          isPharmaManufacturing(weaveDomain)
            ? 'LIMS, MES, ELN extracts, and relational tables'
            : 'Connect to various databases to extract structured knowledge',
        icon: ServerIcon,
        features: isPharmaManufacturing(weaveDomain) ? pharmaDbFeatures : [
          'Support for MongoDB, PostgreSQL, MySQL',
          'Automatic schema detection',
          'Query optimization and indexing',
          'Real-time data synchronization',
          'Secure connection management',
        ],
        color: 'green',
        gradient: 'from-green-500 to-green-600',
      },
      {
        id: 'servicenow',
        title: isPharmaManufacturing(weaveDomain) ? 'Quality ITSM & exports' : 'ServiceNow Data',
        description:
          isPharmaManufacturing(weaveDomain)
            ? 'ServiceNow or spreadsheet exports for deviations, CAPA, and tasks'
            : 'Import data from ServiceNow to create knowledge fabric from tickets, incidents, and knowledge articles',
        icon: CloudIcon,
        features: isPharmaManufacturing(weaveDomain) ? pharmaSnFeatures : [
          'Import from CSV/Excel files',
          'Direct ServiceNow API connection',
          'Process tickets and incidents',
          'Extract knowledge articles',
          'Real-time data synchronization',
        ],
        color: 'orange',
        gradient: 'from-orange-500 to-orange-600',
      },
      {
        id: 'codebase',
        title: 'Codebase / Workspace',
        description:
          'Upload a zip/folder or clone a git repo to build a code knowledge graph and migration JSON',
        icon: CodeBracketSquareIcon,
        features: [
          'Zip, folder, or git clone (public / PAT / SSH)',
          'Multi-language structural analysis',
          'LLM enrichment via Bedrock or OpenAI',
          'Typed knowledge graph + migration waves',
          'Download complete migration JSON',
        ],
        color: 'cyan',
        gradient: 'from-cyan-500 to-blue-600',
      },
      {
        id: 'composite',
        title: 'Composite Multi-Source Fabric',
        description:
          isPharmaManufacturing(weaveDomain)
            ? 'Merge pharma document, database, and ITSM fabrics into one governed fabric'
            : 'Combine existing PDF, database, and ServiceNow fabrics into one unified fabric',
        icon: Squares2X2Icon,
        features: isPharmaManufacturing(weaveDomain) ? pharmaCompFeatures : [
          'Merge multiple source fabrics',
          'Unified querying across sources',
          'Cross-source lineage in one fabric',
          'Smart way to combine PDF + DB',
          'No duplicate source re-ingestion',
        ],
        color: 'violet',
        gradient: 'from-violet-500 to-fuchsia-600',
      },
    ];
  }, [weaveDomain]);

  const handleCreateKnowledge = async () => {
    if (!selectedOption) return;
    
    if (selectedOption === 'pdf') {
      setShowPDFUpload(true);
      return;
    }

    if (selectedOption === 'codebase') {
      setShowCodebaseFabric(true);
      return;
    }
    
    if (selectedOption === 'database') {
      setShowDatabaseFabric(true);
      return;
    }
    
    if (selectedOption === 'servicenow') {
      setShowServiceNowFabric(true);
      return;
    }

    if (selectedOption === 'composite') {
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
    setShowProgress(false);
    if (selectedOption === 'composite' && compositePendingSourceType === 'pdf') {
      setCompositeSourceIds((prev) => (prev.includes(fabricId) ? prev : [...prev, fabricId]));
      setCompositePendingSourceType(null);
      loadAvailableFabrics();
      return;
    }
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
    
    const openNow = window.confirm(`${successMessage}\n\nOpen Knowledge Graph now?`);
    if (openNow) {
      navigate(`/fabrics/${fabricId}/knowledge-graph`);
    }
    
    console.log('Knowledge fabric created successfully:', fabricId);
  };

  const handleProgressError = (error: string) => {
    setShowProgress(false);
    console.error('Knowledge fabric creation failed:', error);
  };

  const handlePDFUploadCancel = () => {
    setShowPDFUpload(false);
    if (selectedOption === 'composite') {
      setCompositePendingSourceType(null);
      return;
    }
    setSelectedOption(null);
  };

  const handleDatabaseFabricComplete = (fabricId: string) => {
    setShowDatabaseFabric(false);
    if (selectedOption === 'composite' && compositePendingSourceType === 'database') {
      setCompositeSourceIds((prev) => (prev.includes(fabricId) ? prev : [...prev, fabricId]));
      setCompositePendingSourceType(null);
      loadAvailableFabrics();
      return;
    }
    setSelectedOption(null);
    
    // Show success message with fabric details
    const successMessage = `🎉 Database Knowledge Fabric Created Successfully!

Fabric ID: ${fabricId}
Status: Active
Training: Completed

You can now view your fabric in the "Available Fabrics" tab with real statistics including:
• Document count
• Chunks count  
• Embedding count
• Training status
• Creation date`;
    
    const openNow = window.confirm(`${successMessage}\n\nOpen Knowledge Graph now?`);
    if (openNow) {
      navigate(`/fabrics/${fabricId}/knowledge-graph`);
    }
    
    console.log('Database knowledge fabric created successfully:', fabricId);
  };

  const handleDatabaseFabricCancel = () => {
    setShowDatabaseFabric(false);
    if (selectedOption === 'composite') {
      setCompositePendingSourceType(null);
      return;
    }
    setCompositePendingSourceType(null);
    setSelectedOption(null);
  };

  const handleServiceNowFabricComplete = (fabricId: string) => {
    setShowServiceNowFabric(false);
    if (selectedOption === 'composite' && compositePendingSourceType === 'servicenow') {
      setCompositeSourceIds((prev) => (prev.includes(fabricId) ? prev : [...prev, fabricId]));
      setCompositePendingSourceType(null);
      loadAvailableFabrics();
      return;
    }
    setSelectedOption(null);
    
    // Show success message with fabric details
    const successMessage = `🎉 ServiceNow Knowledge Fabric Created Successfully!

Fabric ID: ${fabricId}
Status: Active
Training: Completed

You can now view your fabric in the "Available Fabrics" tab with real statistics including:
• ServiceNow data count
• Chunks count  
• Embedding count
• Training status
• Creation date`;
    
    const openNow = window.confirm(`${successMessage}\n\nOpen Knowledge Graph now?`);
    if (openNow) {
      navigate(`/fabrics/${fabricId}/knowledge-graph`);
    }
    
    console.log('ServiceNow knowledge fabric created successfully:', fabricId);
  };

  const handleServiceNowFabricCancel = () => {
    setShowServiceNowFabric(false);
    if (selectedOption === 'composite') {
      setCompositePendingSourceType(null);
      return;
    }
    setCompositePendingSourceType(null);
    setSelectedOption(null);
  };

  const handleCompositeAddSource = (sourceType: 'pdf' | 'database' | 'servicenow') => {
    setCompositePendingSourceType(sourceType);
    if (sourceType === 'pdf') setShowPDFUpload(true);
    if (sourceType === 'database') setShowDatabaseFabric(true);
    if (sourceType === 'servicenow') setShowServiceNowFabric(true);
  };

  const toggleCompositeSource = (sourceId: string) => {
    setCompositeSourceIds((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  };

  const handleCreateCompositeFabric = async () => {
    if (compositeSourceIds.length < 2) {
      alert('Please select at least two source fabrics to create a composite fabric.');
      return;
    }
    setIsCreatingComposite(true);
    try {
      const response = await apiRequest('api/v1/knowledge/create-composite-fabric', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: compositeName || `Composite_Fabric_${Date.now()}`,
          source_ids: compositeSourceIds,
          description: `Composite fabric built from ${compositeSourceIds.length} sources`,
          tags: ['composite', 'multi-source'],
          weave_domain: weaveDomain,
          guardrails,
        })
      });
      const payload = await response.json();
      if (!payload.success) {
        throw new Error(payload.error || payload.message || 'Failed to create composite fabric');
      }
      alert(`🎉 Composite Fabric Created!\n\nFabric ID: ${payload.data.source_id}\nSources Combined: ${payload.data.source_count}`);
      setSelectedOption(null);
      setCompositeName('');
      setCompositeSourceIds([]);
      const refresh = await apiRequest('api/v1/knowledge/');
      const refreshPayload = await refresh.json();
      if (refreshPayload.success && Array.isArray(refreshPayload.data)) {
        setAvailableFabrics(refreshPayload.data);
      }
    } catch (error) {
      alert(`Failed to create composite fabric: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsCreatingComposite(false);
    }
  };

  const handleUploadHandbookFiles = async () => {
    if (handbookUploadFiles.length === 0 || isUploadingHandbook) return;
    try {
      setIsUploadingHandbook(true);
      const formData = new FormData();
      handbookUploadFiles.forEach((file) => formData.append('files', file));
      const response = await apiRequest('api/v1/upload/', {
        method: 'POST',
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || payload?.message || 'Failed to upload handbook file(s)');
      }
      const uploaded = ((payload?.data?.results || []) as Array<{ status?: string; file?: string; file_path?: string }>)
        .filter((r) => r.status === 'success')
        .map((r) => r.file || r.file_path || '')
        .filter(Boolean);
      setGuardrails((prev) => ({
        ...prev,
        handbook_files: Array.from(new Set([...(prev.handbook_files || []), ...uploaded])),
      }));
      setHandbookUploadFiles([]);
    } catch (error) {
      alert(`Failed to upload handbook file(s): ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUploadingHandbook(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0] [&_textarea]:bg-[#10141d]/70 [&_textarea]:text-[#e8edf4] [&_textarea]:border-[rgba(148,163,184,0.2)] [&_textarea]:placeholder:text-[#8b9cb0] [&_select]:bg-[#10141d]/70 [&_select]:text-[#e8edf4] [&_select]:border-[rgba(148,163,184,0.2)]">
      {/* PDF Upload Modal */}
      {showPDFUpload && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50">
          <div className="bg-[#10141d]/92 rounded-2xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-[rgba(148,163,184,0.2)] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
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
        weaveDomain={weaveDomain}
        connectorProfile={connectorProfile}
        guardrails={guardrails}
      />

      {/* Database Knowledge Fabric Modal */}
      {showDatabaseFabric && (
        <DatabaseKnowledgeFabric
          onComplete={handleDatabaseFabricComplete}
          onCancel={handleDatabaseFabricCancel}
          weaveDomain={weaveDomain}
          connectorProfile={connectorProfile}
          guardrails={guardrails}
        />
      )}

      {/* ServiceNow Knowledge Fabric Modal */}
      {showServiceNowFabric && (
        <ServiceNowKnowledgeFabric
          isVisible={showServiceNowFabric}
          onComplete={handleServiceNowFabricComplete}
          onCancel={handleServiceNowFabricCancel}
          weaveDomain={weaveDomain}
          connectorProfile={connectorProfile}
          guardrails={guardrails}
        />
      )}

      {showCodebaseFabric && (
        <CodebaseKnowledgeFabric
          onClose={() => setShowCodebaseFabric(false)}
          weaveDomain={weaveDomain}
          onCreated={(fabricId) => {
            setShowCodebaseFabric(false);
            setSelectedOption(null);
            loadAvailableFabrics();
            navigate(`/fabrics/${fabricId}/knowledge-graph`);
          }}
        />
      )}

      <nav className="mb-10 flex flex-wrap items-center justify-center gap-2 text-xs sm:text-sm text-[#8b9cb0]" aria-label="Weave journey">
        <span className="rounded-full border border-[rgba(94,200,242,0.4)] bg-[rgba(94,200,242,0.14)] px-3 py-1.5 font-medium text-[#5ec8f2]">
          Create Fabric
        </span>
        <span aria-hidden className="text-[#64748b]">→</span>
        <Link
          to="/fabrics"
          className="rounded-full border border-[rgba(148,163,184,0.2)] px-3 py-1.5 text-[#cbd5e1] hover:border-[rgba(94,200,242,0.35)] hover:text-[#e8edf4] transition-colors"
        >
          View Knowledge Graph
        </Link>
        <span aria-hidden className="text-[#64748b]">→</span>
        <Link
          to="/ontology"
          className="rounded-full border border-[rgba(148,163,184,0.2)] px-3 py-1.5 text-[#cbd5e1] hover:border-[rgba(94,200,242,0.35)] hover:text-[#e8edf4] transition-colors"
        >
          Discover Ontology
        </Link>
        <span aria-hidden className="text-[#64748b]">→</span>
        <Link
          to="/ontology/enrichment"
          className="rounded-full border border-[rgba(148,163,184,0.2)] px-3 py-1.5 text-[#cbd5e1] hover:border-[rgba(94,200,242,0.35)] hover:text-[#e8edf4] transition-colors"
        >
          Enrich Ontology
        </Link>
      </nav>

      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex items-center justify-center mb-4">
          <div className="p-3 rounded-full bg-[#10141d]/80 backdrop-blur-xl border border-[rgba(148,163,184,0.2)] shadow-lg shadow-black/30">
            {isPharmaManufacturing(weaveDomain) ? (
              <BeakerIcon className="h-8 w-8 text-[#a78bfa]" />
            ) : (
              <SparklesIcon className="h-8 w-8 text-[#5ec8f2]" />
            )}
          </div>
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Create Knowledge Fabric
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          {isPharmaManufacturing(weaveDomain)
            ? 'Ingest scientific manufacturing artifacts, classify sources, and stage a governed fabric for the same Weave journey.'
            : `Build a ${selectedKindMeta.label.toLowerCase()} — Weave will apply domain intelligence so agents and Test with LLM can answer complex questions.`}
        </p>

        <div className="mt-8 max-w-5xl mx-auto text-left">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <span className="text-xs uppercase tracking-[0.18em] text-[#8b9cb0]">
              What kind of fabric are you creating?
            </span>
            <span className="text-xs text-[#64748b]">
              Weave adds domain intelligence for agents &amp; Test with LLM
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {FABRIC_KIND_OPTIONS.map((kind) => {
              const selected = weaveDomain === kind.id;
              return (
                <button
                  key={kind.id}
                  type="button"
                  onClick={() => {
                    setWeaveDomainState(kind.id);
                    setSelectedOption(null);
                    if (kind.showsPharmaWorkspace) {
                      setSelectedOption('pdf');
                      setPharmaConnector('pdf');
                    }
                  }}
                  className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                    selected
                      ? 'border-[rgba(94,200,242,0.45)] bg-[rgba(94,200,242,0.14)] text-[#e8edf4]'
                      : 'border-[rgba(148,163,184,0.2)] bg-white/[0.02] text-[#cbd5e1] hover:bg-white/[0.05]'
                  }`}
                >
                  <span className="block text-sm font-semibold">{kind.label}</span>
                  <span className="block text-[11px] text-[#8b9cb0] mt-1 leading-snug">{kind.description}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-[#8b9cb0] text-center sm:text-left">
            Selected: <span className="text-[#5ec8f2] font-medium">{selectedKindMeta.label}</span>
            {' — '}
            agents and Test with LLM will reason with this domain lens.
          </p>
        </div>

        {isPharmaManufacturing(weaveDomain) && (
          <div className="mt-8 max-w-4xl mx-auto text-left rounded-2xl border border-[rgba(155,139,212,0.25)] bg-[rgba(155,139,212,0.06)] p-5">
            <p className="text-sm font-semibold text-[#e8edf4] mb-3">Source connector</p>
            <p className="text-xs text-[#8b9cb0] mb-4">
              Map your ingestion path: documents (PDF/TXT), structured systems (DB/LIMS), ITSM quality feeds (ServiceNow-style), or a composite of existing fabrics.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {(
                [
                  { id: 'pdf' as const, label: 'Documents & reports', sub: 'PDF / TXT' },
                  { id: 'database' as const, label: 'LIMS / MES / ELN / DB', sub: 'Tables & exports' },
                  { id: 'servicenow' as const, label: 'Quality ITSM', sub: 'CSV / API' },
                  { id: 'composite' as const, label: 'Composite', sub: 'Merge fabrics' },
                ]
              ).map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => {
                    setPharmaConnector(c.id);
                    setSelectedOption(c.id);
                  }}
                  className={`rounded-xl border px-3 py-3 text-left text-sm transition-colors ${
                    pharmaConnector === c.id && selectedOption === c.id
                      ? 'border-[rgba(167,139,250,0.5)] bg-[rgba(167,139,250,0.15)] text-[#e8edf4]'
                      : 'border-[rgba(148,163,184,0.2)] bg-white/[0.02] text-[#cbd5e1] hover:bg-white/[0.05]'
                  }`}
                >
                  <span className="block font-medium">{c.label}</span>
                  <span className="block text-[11px] text-[#8b9cb0] mt-0.5">{c.sub}</span>
                </button>
              ))}
            </div>

            <p className="text-sm font-semibold text-[#e8edf4] mt-6 mb-2">Artifact types (ingestion hints)</p>
            <div className="flex flex-wrap gap-2">
              {[
                ['experiment_reports', 'Experiment reports'],
                ['batch_records', 'Batch records'],
                ['lab_files', 'Lab files'],
                ['lims_mes_eln', 'LIMS / MES / ELN'],
                ['sops', 'SOPs'],
                ['protocols', 'Protocols'],
                ['analytical_tests', 'Analytical tests'],
                ['stability', 'Stability reports'],
                ['deviation_capa', 'Deviation / CAPA'],
                ['databases_tables', 'Databases / tables'],
              ].map(([key, label]) => (
                <label
                  key={key}
                  className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs cursor-pointer ${
                    pharmaArtifacts[key]
                      ? 'border-[rgba(94,200,242,0.4)] bg-[rgba(94,200,242,0.1)] text-[#cfefff]'
                      : 'border-[rgba(148,163,184,0.2)] text-[#8b9cb0]'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="rounded border-[rgba(148,163,184,0.3)]"
                    checked={!!pharmaArtifacts[key]}
                    onChange={() =>
                      setPharmaArtifacts((prev) => ({ ...prev, [key]: !prev[key] }))
                    }
                  />
                  {label}
                </label>
              ))}
            </div>

            <div className="mt-5">
              <div className="flex justify-between text-xs text-[#8b9cb0] mb-1">
                <span>Fabric readiness score</span>
                <span className="text-[#5ec8f2] font-semibold">{fabricReadinessScore}%</span>
              </div>
              <div className="h-2 rounded-full bg-[#0f1728] border border-[rgba(148,163,184,0.15)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#8b5cf6] via-[#5ec8f2] to-[#3ecf9b] transition-all duration-500"
                  style={{ width: `${fabricReadinessScore}%` }}
                />
              </div>
              <p className="text-[11px] text-[#64748b] mt-2">
                Raises with connector selection, artifact hints, and staged ontology alignment. Final outputs include indexed artifacts, entities, relationships, evidence mapping, staged graph, and domain metadata.
              </p>
            </div>
          </div>
        )}
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
            onClick={() => {
              setSelectedOption(option.id);
              if (
                isPharmaManufacturing(weaveDomain) &&
                (option.id === 'pdf' || option.id === 'database' || option.id === 'servicenow' || option.id === 'composite')
              ) {
                setPharmaConnector(option.id);
              }
            }}
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
        <div className="rounded-2xl p-8 border border-[rgba(148,163,184,0.2)] bg-[#10141d]/75 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div className="text-center">
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              {selectedOption === 'composite' ? 'Build Composite Multi-Source Fabric' : 'Ready to Create Your Knowledge Fabric?'}
            </h3>
            <p className="text-gray-600 mb-8 max-w-2xl mx-auto">
              {selectedOption === 'composite'
                ? 'Select at least two existing source fabrics (PDF/Database/ServiceNow) and create one unified composite fabric.'
                : 'Your knowledge fabric will be created in the local vector database and the model will be automatically trained for optimal performance.'}
            </p>
            <div className="mb-8 rounded-2xl border border-[rgba(94,200,242,0.32)] bg-gradient-to-br from-[rgba(94,200,242,0.1)] to-[rgba(155,139,212,0.08)] p-5 text-left">
              <p className="text-sm font-semibold text-[#e8edf4] mb-1">Data Governance & Security Guardrails</p>
              <p className="text-xs text-[#8b9cb0] mb-4">
                Attach governance policies to this fabric at creation time. These settings travel with the fabric and can be updated later.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                <label className="text-xs text-[#8b9cb0]">
                  Data classification
                  <select
                    value={guardrails.data_classification}
                    onChange={(e) =>
                      setGuardrails((prev) => ({
                        ...prev,
                        data_classification: e.target.value as FabricGuardrails['data_classification'],
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                  >
                    <option value="public">Public</option>
                    <option value="internal">Internal</option>
                    <option value="confidential">Confidential</option>
                    <option value="restricted">Restricted</option>
                  </select>
                </label>
                <label className="text-xs text-[#8b9cb0]">
                  Compliance tags (comma separated)
                  <input
                    value={guardrails.compliance_tags.join(', ')}
                    onChange={(e) =>
                      setGuardrails((prev) => ({
                        ...prev,
                        compliance_tags: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                    placeholder="HIPAA, SOC2, GDPR"
                  />
                </label>
                <label className="text-xs text-[#8b9cb0]">
                  PII fields (comma separated)
                  <input
                    value={guardrails.pii_fields.join(', ')}
                    onChange={(e) =>
                      setGuardrails((prev) => ({
                        ...prev,
                        pii_fields: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                    placeholder="ssn, member_id, email"
                  />
                </label>
                <label className="text-xs text-[#8b9cb0]">
                  Approved roles (comma separated)
                  <input
                    value={guardrails.approved_roles.join(', ')}
                    onChange={(e) =>
                      setGuardrails((prev) => ({
                        ...prev,
                        approved_roles: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] px-2 py-1.5 text-sm"
                    placeholder="admin, compliance_officer"
                  />
                </label>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-[#cbd5e1]">
                <label className="inline-flex items-center gap-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] px-2 py-2">
                  <input
                    type="checkbox"
                    checked={guardrails.enforce_masking}
                    onChange={() => setGuardrails((prev) => ({ ...prev, enforce_masking: !prev.enforce_masking }))}
                  />
                  Enforce masking
                </label>
                <label className="inline-flex items-center gap-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] px-2 py-2">
                  <input
                    type="checkbox"
                    checked={guardrails.encryption_at_rest}
                    onChange={() => setGuardrails((prev) => ({ ...prev, encryption_at_rest: !prev.encryption_at_rest }))}
                  />
                  Encryption at rest
                </label>
                <label className="inline-flex items-center gap-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] px-2 py-2">
                  <input
                    type="checkbox"
                    checked={guardrails.encryption_in_transit}
                    onChange={() => setGuardrails((prev) => ({ ...prev, encryption_in_transit: !prev.encryption_in_transit }))}
                  />
                  Encryption in transit
                </label>
                <label className="inline-flex items-center gap-2 rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] px-2 py-2">
                  <input
                    type="checkbox"
                    checked={guardrails.row_level_security}
                    onChange={() => setGuardrails((prev) => ({ ...prev, row_level_security: !prev.row_level_security }))}
                  />
                  Row-level security
                </label>
              </div>
              <div className="mt-4 rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-3">
                <p className="text-xs text-[#8b9cb0] mb-2">Upload governance handbook / policy documents</p>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.doc,.docx,.md"
                    onChange={(e) => setHandbookUploadFiles(Array.from(e.target.files || []))}
                    className="text-xs"
                  />
                  <button
                    type="button"
                    onClick={handleUploadHandbookFiles}
                    disabled={isUploadingHandbook || handbookUploadFiles.length === 0}
                    className="rounded-md border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.14)] px-3 py-1.5 text-xs text-[#cfefff] disabled:opacity-50"
                  >
                    {isUploadingHandbook ? 'Uploading...' : 'Upload Handbook'}
                  </button>
                </div>
                {guardrails.handbook_files.length > 0 && (
                  <div className="mt-2 text-[11px] text-[#cbd5e1]">
                    Attached: {guardrails.handbook_files.join(', ')}
                  </div>
                )}
              </div>
            </div>

            {selectedOption !== 'composite' ? (
              <div className="flex items-center justify-center space-x-4">
                <button
                  onClick={handleCreateKnowledge}
                  disabled={isCreating}
                  className={`px-8 py-4 border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30 text-[#e8edf4] font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center space-x-2 ${
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
            ) : (
              <div className="max-w-5xl mx-auto text-left space-y-4">
                <div className="rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-4">
                  <div className="text-sm font-semibold text-[#e8edf4] mb-3">Add New Source Inline</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <button
                      type="button"
                      onClick={() => handleCompositeAddSource('pdf')}
                      className="rounded-lg border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] px-3 py-2 text-sm text-[#cfefff] hover:bg-[rgba(94,200,242,0.15)]"
                    >
                      + Add PDF Source
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCompositeAddSource('database')}
                      className="rounded-lg border border-[rgba(62,207,155,0.25)] bg-[rgba(62,207,155,0.08)] px-3 py-2 text-sm text-[#c5f5e4] hover:bg-[rgba(62,207,155,0.15)]"
                    >
                      + Add Database Source
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCompositeAddSource('servicenow')}
                      className="rounded-lg border border-[rgba(251,146,60,0.25)] bg-[rgba(251,146,60,0.08)] px-3 py-2 text-sm text-[#ffe0c2] hover:bg-[rgba(251,146,60,0.15)]"
                    >
                      + Add ServiceNow Source
                    </button>
                  </div>
                  <div className="mt-2 text-xs text-[#8b9cb0]">
                    Newly created sources are automatically added to the source basket.
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                  <div className="md:col-span-8">
                    <label className="block text-xs uppercase tracking-[0.16em] text-[#8b9cb0] mb-2">Composite Fabric Name</label>
                    <input
                      value={compositeName}
                      onChange={(e) => setCompositeName(e.target.value)}
                      placeholder="Member360_Claims_Policy_Composite"
                      className="w-full border border-[rgba(148,163,184,0.2)] rounded-lg px-4 py-2.5"
                    />
                  </div>
                  <div className="md:col-span-4">
                    <button
                      onClick={handleCreateCompositeFabric}
                      disabled={isCreatingComposite || compositeSourceIds.length < 2}
                      className="w-full px-6 py-2.5 border border-[rgba(167,139,250,0.35)] bg-gradient-to-r from-violet-500/30 to-fuchsia-500/30 text-[#e8edf4] font-semibold rounded-lg disabled:opacity-50"
                    >
                      {isCreatingComposite ? 'Creating Composite...' : `Create Composite (${compositeSourceIds.length})`}
                    </button>
                  </div>
                </div>
                <div className="rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-sm font-semibold text-[#e8edf4]">Source Basket</div>
                    <div className="text-xs text-[#8b9cb0]">
                      {loadingAvailableFabrics ? 'Loading sources...' : `${eligibleCompositeSources.length} sources available`}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-64 overflow-auto pr-1">
                    {eligibleCompositeSources.map((source) => {
                      const active = compositeSourceIds.includes(source.id);
                      return (
                        <button
                          type="button"
                          key={source.id}
                          onClick={() => toggleCompositeSource(source.id)}
                          className={`text-left rounded-lg border px-3 py-3 transition ${
                            active
                              ? 'border-[rgba(94,200,242,0.45)] bg-[rgba(94,200,242,0.14)]'
                              : 'border-[rgba(148,163,184,0.2)] bg-white/[0.02] hover:bg-white/[0.05]'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-[#e8edf4] truncate pr-2">{source.name}</span>
                            <span className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">{source.source_type}</span>
                          </div>
                          <div className="mt-1 text-xs text-[#8b9cb0]">
                            {source.document_count || 0} docs • {source.total_chunks || 0} chunks
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Progress Steps */}
            {isCreating && selectedOption !== 'composite' && (
              <div className="mt-8">
                <div className="flex items-center justify-center space-x-8 rounded-xl border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-4">
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-[rgba(62,207,155,0.2)] border border-[rgba(62,207,155,0.4)] rounded-full flex items-center justify-center">
                      <CheckCircleIcon className="h-5 w-5 text-white" />
                    </div>
                    <span className="ml-2 text-sm font-medium text-[#cbd5e1]">Processing Data</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-[rgba(94,200,242,0.2)] border border-[rgba(94,200,242,0.4)] rounded-full flex items-center justify-center">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    </div>
                    <span className="ml-2 text-sm font-medium text-[#cbd5e1]">Creating Embeddings</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-white/[0.06] border border-[rgba(148,163,184,0.2)] rounded-full flex items-center justify-center">
                      <CpuChipIcon className="h-5 w-5 text-[#8b9cb0]" />
                    </div>
                    <span className="ml-2 text-sm font-medium text-[#8b9cb0]">Training Model</span>
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