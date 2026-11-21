import React, { useState } from 'react';

export type FabricProgressStep = {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  icon?: React.ComponentType<{ className?: string }>;
};

interface FabricCreationProgressModalProps {
  isVisible: boolean;
  title: string;
  subtitle?: string;
  overallProgress: number;
  steps: FabricProgressStep[];
  /** Live status line. Fades each time it changes. */
  statusText?: string;
  fabricId?: string;
  onOpen?: (fabricId: string) => void;
  onDismiss?: (fabricId: string) => void;
  footer?: React.ReactNode;
}

const FabricCreationProgressModal: React.FC<FabricCreationProgressModalProps> = ({
  isVisible,
  title,
  overallProgress,
  steps,
  statusText,
  fabricId,
  onOpen,
  onDismiss,
  footer,
}) => {
  const [copied, setCopied] = useState(false);
  if (!isVisible) return null;

  const errored = steps.find((step) => step.status === 'error');
  const active = steps.find((step) => step.status === 'processing');
  const finished = Boolean(fabricId);
  const line = finished ? 'Completed' : errored ? 'Could not finish' : (statusText || active?.title || 'Preparing');
  const pct = Math.max(0, Math.min(100, finished ? 100 : overallProgress));

  const copyId = async () => {
    if (!fabricId) return;
    try {
      await navigator.clipboard.writeText(fabricId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/55 px-6 backdrop-blur-2xl">
      <div className="w-full max-w-[22rem] rounded-[28px] border border-white/10 bg-[#0c0e12]/88 px-8 py-9 text-center shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-white/40">
          {finished ? 'Knowledge Fabric' : title}
        </p>

        <p key={line} className="kf-status-line mt-5 text-[22px] font-medium tracking-[-0.03em] text-white">
          {finished ? 'Completed' : line}
        </p>

        <div className="mx-auto mt-6 h-[3px] w-full overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-white transition-[width] duration-700 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>

        {finished && fabricId && (
          <div className="kf-status-line mt-8">
            <p className="text-[11px] uppercase tracking-[0.18em] text-white/35">KF ID</p>
            <p className="mt-2 break-all font-mono text-[12px] leading-relaxed text-white/80">{fabricId}</p>
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                type="button"
                onClick={copyId}
                className="rounded-full bg-white/10 px-4 py-2 text-[13px] font-medium text-white transition hover:bg-white/16"
              >
                {copied ? 'Copied' : 'Copy ID'}
              </button>
              {onOpen && (
                <button
                  type="button"
                  onClick={() => onOpen(fabricId)}
                  className="rounded-full bg-[#f5f5f7] px-4 py-2 text-[13px] font-medium text-[#111113] transition hover:bg-[#ffffff]"
                >
                  Open
                </button>
              )}
            </div>
            {onDismiss && (
              <button
                type="button"
                onClick={() => onDismiss(fabricId)}
                className="mt-4 text-[13px] text-white/45 transition hover:text-white/80"
              >
                Done
              </button>
            )}
          </div>
        )}

        {errored && !finished && (
          <div className="kf-status-line mt-6">
            <p className="text-[13px] leading-relaxed text-[#f08984]">{errored.description}</p>
            {onDismiss && (
              <button
                type="button"
                onClick={() => onDismiss('')}
                className="mt-5 text-[13px] text-white/55 transition hover:text-white/80"
              >
                Close
              </button>
            )}
          </div>
        )}

        {footer}
      </div>
    </div>
  );
};

export default FabricCreationProgressModal;
