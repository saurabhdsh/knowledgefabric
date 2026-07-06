import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { apiRequest } from '../utils/api';
import {
  CpuChipIcon,
  DocumentTextIcon,
  ServerIcon,
  CheckCircleIcon,
  SparklesIcon,
  BeakerIcon,
  GlobeAltIcon,
  Squares2X2Icon,
  LinkIcon,
} from '@heroicons/react/24/outline';
import type { WeaveDomain } from '../utils/weaveDomain';
import FabricCreationProgressModal from './FabricCreationProgressModal';

interface ProgressStep {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
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

function buildGenericSteps(): ProgressStep[] {
  return [
    {
      id: 'extract',
      title: 'Extracting Text Content',
      description: 'Processing PDF documents and extracting text content',
      icon: DocumentTextIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'chunk',
      title: 'Creating Text Chunks',
      description: 'Splitting content into intelligent chunks for better understanding',
      icon: BeakerIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'embed',
      title: 'Generating Embeddings',
      description: 'Creating vector embeddings for semantic search',
      icon: SparklesIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'store',
      title: 'Storing in Vector Database',
      description: 'Saving embeddings to local ChromaDB',
      icon: ServerIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'train',
      title: 'Optimizing Retrieval Index',
      description: 'Calibrating semantic retrieval and ranking signals',
      icon: CpuChipIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'ready',
      title: 'Knowledge Fabric Ready',
      description: 'Your fabric is indexed and ready for agents',
      icon: GlobeAltIcon,
      status: 'pending',
      progress: 0,
    },
  ];
}

function buildPharmaSteps(): ProgressStep[] {
  return [
    {
      id: 'ingest',
      title: 'Ingest scientific artifacts',
      description: 'Normalize experiment reports, batch records, SOPs, protocols, and lab files',
      icon: DocumentTextIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'classify',
      title: 'Artifact classification & metadata',
      description: 'Auto-classify artifact types and extract scientific metadata fields',
      icon: BeakerIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'context',
      title: 'Batch / experiment / product context',
      description: 'Detect batch lineage hooks, study IDs, product codes, and equipment references',
      icon: Squares2X2Icon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'graph',
      title: 'Entities, relationships & evidence',
      description: 'Stage preliminary entities, relationships, and evidence spans for the knowledge graph',
      icon: LinkIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'embed',
      title: 'Embeddings & domain metadata',
      description: 'Vectorize content and attach domain-specific structured metadata',
      icon: SparklesIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'store',
      title: 'Indexed fabric & staged graph',
      description: 'Persist indexed artifacts and staged graph projection for exploration',
      icon: ServerIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'ready',
      title: 'Pharma fabric ready',
      description: 'Proceed to Knowledge Graph, Ontology Discovery, then Enrichment',
      icon: GlobeAltIcon,
      status: 'pending',
      progress: 0,
    },
  ];
}

const STEP_DURATIONS_GENERIC_MS = [1500, 1200, 2000, 1500, 1500, 1000];
const STEP_DURATIONS_PHARMA_MS = [1400, 1600, 1400, 1800, 1900, 1500, 1100];

interface KnowledgeFabricProgressProps {
  isVisible: boolean;
  onComplete: (fabricId: string) => void;
  onError: (error: string) => void;
  uploadedFiles: string[];
  weaveDomain?: WeaveDomain;
  connectorProfile?: string | null;
  guardrails?: FabricGuardrails;
}

const KnowledgeFabricProgress: React.FC<KnowledgeFabricProgressProps> = ({
  isVisible,
  onComplete,
  onError,
  uploadedFiles,
  weaveDomain = 'generic',
  connectorProfile,
  guardrails,
}) => {
  const [fabricId, setFabricId] = useState<string>('');
  const [overallProgress, setOverallProgress] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  const definition = useMemo(() => {
    const pharma = weaveDomain === 'pharma';
    const steps = pharma ? buildPharmaSteps() : buildGenericSteps();
    const durations = pharma ? STEP_DURATIONS_PHARMA_MS : STEP_DURATIONS_GENERIC_MS;
    return { steps, durations };
  }, [weaveDomain]);

  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>(() => definition.steps);

  useEffect(() => {
    if (!isVisible) return;
    setFabricId('');
    setIsProcessing(false);
    setOverallProgress(0);
    const fresh = weaveDomain === 'pharma' ? buildPharmaSteps() : buildGenericSteps();
    setProgressSteps(fresh.map((s) => ({ ...s, status: 'pending' as const, progress: 0 })));
  }, [isVisible, weaveDomain]);

  const simulateProgress = useCallback(
    async (stepIndex: number, targetProgress: number, duration: number, stepTotal: number) => {
      const startTime = Date.now();
      return new Promise<void>((resolve) => {
        const updateProgress = () => {
          const elapsed = Date.now() - startTime;
          const progress = Math.min((elapsed / duration) * targetProgress, targetProgress);

          setProgressSteps((prev) =>
            prev.map((step, index) => (index === stepIndex ? { ...step, progress } : step))
          );

          setOverallProgress(((stepIndex + progress / 100) / stepTotal) * 100);

          if (progress < targetProgress) {
            requestAnimationFrame(updateProgress);
          } else {
            resolve();
          }
        };

        updateProgress();
      });
    },
    []
  );

  const updateStep = async (stepIndex: number, status: ProgressStep['status']) => {
    setProgressSteps((prev) =>
      prev.map((step, index) => (index === stepIndex ? { ...step, status } : step))
    );
  };

  const startKnowledgeFabricCreation = async () => {
    const { steps, durations } = definition;
    const n = steps.length;
    try {
      setIsProcessing(true);
      setProgressSteps(steps.map((step) => ({ ...step, status: 'pending' as const, progress: 0 })));
      setOverallProgress(0);
      setFabricId('');

      const body: Record<string, unknown> = {
        files: uploadedFiles,
        source_type: 'pdf',
        train_model: false,
        weave_domain: weaveDomain,
      };
      if (connectorProfile) body.connector_profile = connectorProfile;
      if (guardrails) body.guardrails = guardrails;

      const response = await apiRequest('api/v1/knowledge/create-pdf-fabric', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create knowledge fabric');
      }

      const result = await response.json();
      const newFabricId = result.data?.source_id || `fabric_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setFabricId(newFabricId);

      for (let i = 0; i < n; i += 1) {
        const ms = durations[i] ?? 1200;
        await updateStep(i, 'processing');
        await simulateProgress(i, 100, ms, n);
        await updateStep(i, 'completed');
      }

      setIsProcessing(false);
      setTimeout(() => {
        onComplete(newFabricId);
      }, 2000);
    } catch (error) {
      console.error('Knowledge fabric creation error:', error);
      setIsProcessing(false);
      onError(error instanceof Error ? error.message : 'Failed to create knowledge fabric');
    }
  };

  const startRef = React.useRef(startKnowledgeFabricCreation);
  startRef.current = startKnowledgeFabricCreation;

  useEffect(() => {
    if (isVisible && !isProcessing && !fabricId) {
      startRef.current();
    }
  }, [isVisible, isProcessing, fabricId]);

  if (!isVisible) return null;

  const pharmaOutputs =
    weaveDomain === 'pharma' && fabricId
      ? [
          'Indexed scientific artifacts with provenance',
          'Extracted entities & preliminary relationships',
          'Evidence mapping and staged graph projection',
          'Domain metadata for batch / experiment / product context',
        ]
      : null;

  return (
    <FabricCreationProgressModal
      isVisible={isVisible}
      title={weaveDomain === 'pharma' ? 'Creating Pharma Knowledge Fabric' : 'Creating Knowledge Fabric'}
      subtitle={`Processing ${uploadedFiles.length} file(s)${
        weaveDomain === 'pharma' ? ' with scientific extraction and graph staging' : ' with a fluid semantic pipeline'
      }`}
      overallProgress={overallProgress}
      steps={progressSteps.map((step) => ({ ...step, icon: step.icon }))}
      footer={
        <>
          {pharmaOutputs && (
            <div className="mt-6 p-4 rounded-xl border border-[rgba(155,139,212,0.28)] bg-[rgba(155,139,212,0.08)]">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#c4b5fd] mb-2">Fabric outputs</p>
              <ul className="text-sm text-[#cbd5e1] space-y-1.5">
                {pharmaOutputs.map((line) => (
                  <li key={line} className="flex gap-2">
                    <span className="text-[#9b8bd4]">•</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {fabricId && (
            <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-400/30 rounded-xl">
              <div className="flex items-center space-x-2">
                <CheckCircleIcon className="h-5 w-5 text-emerald-300" />
                <span className="text-sm font-medium text-emerald-200">Knowledge Fabric Created Successfully!</span>
              </div>
              <p className="text-xs text-emerald-300/90 mt-1">Fabric ID: {fabricId}</p>
              <p className="text-xs text-emerald-300/90 mt-1">
                View the graph from Available Fabrics, then continue with Ontology Discovery and Enrichment on the same Weave journey.
              </p>
            </div>
          )}

          {isProcessing && !fabricId && (
            <div className="mt-6 p-4 bg-cyan-500/10 border border-cyan-400/30 rounded-xl">
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-cyan-300" />
                <span className="text-sm font-medium text-cyan-100">Processing your knowledge fabric...</span>
              </div>
              <p className="text-xs text-cyan-200/85 mt-1">Starting ingestion and indexing.</p>
            </div>
          )}
        </>
      }
    />
  );
};

export default KnowledgeFabricProgress;
