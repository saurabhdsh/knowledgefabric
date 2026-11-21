import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { apiRequest } from '../utils/api';
import {
  CpuChipIcon,
  DocumentTextIcon,
  ServerIcon,
  SparklesIcon,
  BeakerIcon,
  GlobeAltIcon,
  Squares2X2Icon,
  LinkIcon,
} from '@heroicons/react/24/outline';
import { isPharmaManufacturing, type WeaveDomain } from '../utils/weaveDomain';
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
      title: 'Profiling & Parsing',
      description: 'Reading layout, headings, tables and pages (OCR when needed)',
      icon: DocumentTextIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'chunk',
      title: 'Modelling Structure',
      description: 'Building section-aware chunks with real page citations',
      icon: BeakerIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'embed',
      title: 'Indexing',
      description: 'Embedding passages with the fabric embedding model',
      icon: SparklesIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'store',
      title: 'Validating',
      description: 'Checking coverage, pages and retrieval round-trip',
      icon: ServerIcon,
      status: 'pending',
      progress: 0,
    },
    {
      id: 'train',
      title: 'Publishing',
      description: 'Marking the fabric active and ready to query',
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

interface KnowledgeFabricProgressProps {
  isVisible: boolean;
  onComplete: (fabricId: string) => void;
  onDismiss?: (fabricId: string) => void;
  onError: (error: string) => void;
  uploadedFiles: string[];
  weaveDomain?: WeaveDomain;
  connectorProfile?: string | null;
  guardrails?: FabricGuardrails;
}

type CreationRun = {
  key: string;
  phase: 'running' | 'done' | 'error';
  statusText: string;
  progress: number;
  fabricId: string;
  error: string;
  listeners: Set<() => void>;
};

let creationRun: CreationRun | null = null;
let armNextAttempt = true;

function publishRun(patch: Partial<CreationRun>) {
  if (!creationRun) return;
  Object.assign(creationRun, patch);
  creationRun.listeners.forEach((listener) => listener());
}

function apiErrorMessage(result: { detail?: unknown; message?: unknown; success?: boolean }, fallback: string): string {
  const detail = result?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
    const message = (detail as { message: string }).message.trim();
    if (message) return message;
  }
  if (typeof result?.message === 'string' && result.message.trim() && result.success === false) return result.message;
  return fallback;
}

const KnowledgeFabricProgress: React.FC<KnowledgeFabricProgressProps> = ({
  isVisible,
  onComplete,
  onDismiss,
  uploadedFiles,
  weaveDomain = 'general',
  connectorProfile,
  guardrails,
}) => {
  const [fabricId, setFabricId] = useState<string>('');
  const [overallProgress, setOverallProgress] = useState(0);
  const [statusText, setStatusText] = useState('Preparing');
  const filesKey = uploadedFiles.join('\n');

  const definition = useMemo(() => {
    const pharma = isPharmaManufacturing(weaveDomain);
    const steps = pharma ? buildPharmaSteps() : buildGenericSteps();
    return { steps };
  }, [weaveDomain]);

  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>(() => definition.steps);

  const applyRun = useCallback((run: CreationRun) => {
    setStatusText(run.statusText);
    setOverallProgress(run.progress);
    setFabricId(run.fabricId);
    if (run.phase === 'done') {
      setProgressSteps((steps) => steps.map((step) => ({ ...step, status: 'completed', progress: 100 })));
    }
    if (run.phase === 'error') {
      setProgressSteps((steps) => steps.map((step, index) => (
        index === 0
          ? { ...step, status: 'error', description: run.error || 'The fabric could not be created.' }
          : { ...step, status: 'pending' }
      )));
    }
  }, []);

  const startKnowledgeFabricCreation = useCallback(async () => {
    const { steps } = definition;
    const phrases = steps.map((step) => step.title);
    let phraseIndex = 0;
    publishRun({ statusText: phrases[0] || 'Preparing', progress: 8, error: '', fabricId: '' });
    setProgressSteps(steps.map((step, index) => ({
      ...step,
      status: index === 0 ? 'processing' : 'pending',
      progress: index === 0 ? 12 : 0,
    })));

    const ticker = window.setInterval(() => {
      phraseIndex = (phraseIndex + 1) % Math.max(phrases.length, 1);
      publishRun({
        statusText: phrases[phraseIndex] || 'Preparing',
        progress: Math.min(92, (creationRun?.progress || 8) + 7),
      });
    }, 1400);

    try {
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
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result?.success === false) {
        throw new Error(apiErrorMessage(result, 'Failed to create knowledge fabric'));
      }

      const newFabricId = String(
        result?.data?.source_id || result?.data?.fabric_id || result?.source_id || ''
      ).trim();
      const buildStatus = String(result?.data?.status || 'active');
      if (!newFabricId) {
        throw new Error('The fabric was created but no KF ID was returned.');
      }
      if (buildStatus === 'failed') {
        throw new Error(String(result?.data?.error || 'The fabric build failed.'));
      }

      window.clearInterval(ticker);
      publishRun({
        phase: 'done',
        fabricId: newFabricId,
        statusText: 'Completed',
        progress: 100,
        error: '',
      });
    } catch (error) {
      window.clearInterval(ticker);
      const message = error instanceof Error ? error.message : 'Failed to create knowledge fabric';
      console.error('Knowledge fabric creation error:', error);
      publishRun({ phase: 'error', error: message, statusText: 'Could not finish', fabricId: '', progress: 100 });
    }
  }, [connectorProfile, definition, guardrails, uploadedFiles, weaveDomain]);

  const startRef = React.useRef(startKnowledgeFabricCreation);
  startRef.current = startKnowledgeFabricCreation;

  useEffect(() => {
    if (!isVisible) {
      if (creationRun?.phase !== 'running') armNextAttempt = true;
      return;
    }
    const key = filesKey;
    const listener = () => {
      if (creationRun && creationRun.key === key) applyRun(creationRun);
    };
    if (
      creationRun
      && creationRun.key === key
      && (creationRun.phase === 'running' || (creationRun.phase === 'done' && !armNextAttempt))
    ) {
      creationRun.listeners.add(listener);
      listener();
      return () => {
        creationRun?.listeners.delete(listener);
      };
    }
    armNextAttempt = false;
    creationRun = {
      key,
      phase: 'running',
      statusText: 'Preparing',
      progress: 0,
      fabricId: '',
      error: '',
      listeners: new Set([listener]),
    };
    setFabricId('');
    setOverallProgress(0);
    setStatusText('Preparing');
    startRef.current();
    return () => {
      creationRun?.listeners.delete(listener);
    };
  }, [applyRun, filesKey, isVisible]);

  if (!isVisible) return null;

  return (
    <FabricCreationProgressModal
      isVisible={isVisible}
      title="Creating Knowledge Fabric"
      overallProgress={overallProgress}
      steps={progressSteps}
      statusText={statusText}
      fabricId={fabricId || undefined}
      onOpen={onComplete}
      onDismiss={onDismiss}
    />
  );
};

export default KnowledgeFabricProgress;
