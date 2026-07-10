import React, { useEffect, useState } from 'react';
import {
  CheckCircleIcon,
  CodeBracketSquareIcon,
  CpuChipIcon,
  ServerIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';

interface CodebaseFabricProgressProps {
  progressId: string;
  onComplete: () => void;
  onClose: () => void;
}

const STAGES = [
  { id: 'stage', label: 'Staging workspace', icon: ServerIcon },
  { id: 'inventory', label: 'Inventory & fingerprint', icon: CodeBracketSquareIcon },
  { id: 'structural', label: 'Structural graph', icon: CpuChipIcon },
  { id: 'enrichment', label: 'LLM enrichment', icon: SparklesIcon },
  { id: 'blueprint', label: 'Migration blueprint', icon: SparklesIcon },
  { id: 'chunks', label: 'Indexing for retrieval', icon: ServerIcon },
  { id: 'done', label: 'Fabric ready', icon: CheckCircleIcon },
];

const CodebaseFabricProgress: React.FC<CodebaseFabricProgressProps> = ({
  progressId,
  onComplete,
  onClose,
}) => {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Starting…');
  const [stage, setStage] = useState('stage');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await apiRequest(`api/v1/knowledge/progress/${progressId}`);
        const payload = await res.json();
        if (!res.ok || payload?.success === false) {
          throw new Error(payload?.detail || payload?.message || 'Progress unavailable');
        }
        const data = payload.data || payload;
        if (cancelled) return;
        setProgress(Number(data.progress || 0));
        setMessage(data.message || 'Processing…');
        setStage(data.stage || 'stage');
        if (data.status === 'error') {
          setError(data.message || 'Analysis failed');
          return;
        }
        if (data.status === 'completed' || Number(data.progress) >= 100) {
          setDone(true);
          setTimeout(() => onComplete(), 1200);
          return;
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to poll progress');
        }
      }
    };
    tick();
    const id = window.setInterval(tick, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [progressId, onComplete]);

  const activeIdx = Math.max(
    0,
    STAGES.findIndex((s) => s.id === stage),
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-[rgba(148,163,184,0.16)] bg-[#0b1220] p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-[#e8edf4]">Analyzing codebase</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-xs uppercase tracking-[0.14em] text-[#8b9cb0] hover:text-[#e8edf4]"
          >
            Close
          </button>
        </div>
        <p className="mt-2 text-sm text-[#8b9cb0]">{message}</p>

        <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className="h-full rounded-full bg-[rgba(94,200,242,0.7)] transition-all duration-500"
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
        <div className="mt-1 text-right text-xs text-[#8b9cb0]">{Math.round(progress)}%</div>

        <ul className="mt-5 space-y-2">
          {STAGES.map((s, idx) => {
            const Icon = s.icon;
            const active = idx === activeIdx;
            const complete = done || idx < activeIdx || progress >= 100;
            return (
              <li
                key={s.id}
                className={`flex items-center gap-3 rounded-xl border px-3 py-2 text-sm ${
                  complete
                    ? 'border-[rgba(62,207,155,0.28)] bg-[rgba(62,207,155,0.08)] text-[#c9f9e6]'
                    : active
                      ? 'border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.1)] text-[#d9f4ff]'
                      : 'border-[rgba(148,163,184,0.1)] text-[#8b9cb0]'
                }`}
              >
                <Icon className="h-4 w-4" />
                {s.label}
              </li>
            );
          })}
        </ul>

        {error && (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default CodebaseFabricProgress;
