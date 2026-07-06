import React from 'react';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

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
  subtitle: string;
  overallProgress: number;
  steps: FabricProgressStep[];
  footer?: React.ReactNode;
}

const FabricCreationProgressModal: React.FC<FabricCreationProgressModalProps> = ({
  isVisible,
  title,
  subtitle,
  overallProgress,
  steps,
  footer,
}) => {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 bg-[#03060d]/82 backdrop-blur-xl flex items-center justify-center z-[60]">
      <div className="relative overflow-hidden bg-[#0b1220]/90 rounded-3xl p-7 max-w-3xl w-full mx-4 border border-[rgba(148,163,184,0.24)] shadow-[0_40px_120px_rgba(2,6,23,0.7),inset_0_1px_0_rgba(255,255,255,0.06)]">
        <div className="pointer-events-none absolute -top-24 -left-16 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl animate-pulse" />
        <div className="pointer-events-none absolute -bottom-24 -right-10 h-56 w-56 rounded-full bg-violet-500/20 blur-3xl animate-pulse" />

        <div className="relative text-center mb-6">
          <h3 className="text-2xl font-semibold text-[#e8edf4] tracking-tight">{title}</h3>
          <p className="text-[#9fb0c5] text-sm mt-1">{subtitle}</p>
        </div>

        <div className="relative mb-6 rounded-xl border border-[rgba(148,163,184,0.22)] bg-white/[0.04] px-4 py-3">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8b9cb0]">
              Overall Progress
            </span>
            <span className="text-sm font-semibold text-[#e8edf4]">
              {Math.round(overallProgress)}%
            </span>
          </div>
          <div className="w-full bg-[#0f1728] rounded-full h-2.5 border border-[rgba(148,163,184,0.14)] overflow-hidden">
            <div
              className="h-2.5 rounded-full transition-all duration-500 bg-[linear-gradient(90deg,#22d3ee_0%,#38bdf8_45%,#818cf8_100%)] shadow-[0_0_20px_rgba(56,189,248,0.45)]"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>

        <div className="space-y-3 relative">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div
                key={step.id}
                className={`relative border rounded-xl p-3 transition-all duration-300 ${
                  step.status === 'completed'
                    ? 'border-emerald-400/35 bg-emerald-400/10'
                    : step.status === 'error'
                    ? 'border-rose-400/35 bg-rose-400/10'
                    : step.status === 'processing'
                    ? 'border-cyan-400/45 bg-cyan-400/12'
                    : 'border-[rgba(148,163,184,0.2)] bg-white/[0.03]'
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    {Icon ? (
                      <Icon
                        className={`h-5 w-5 mt-0.5 ${
                          step.status === 'processing'
                            ? 'text-cyan-300 animate-pulse'
                            : step.status === 'completed'
                            ? 'text-emerald-300'
                            : step.status === 'error'
                            ? 'text-rose-300'
                            : 'text-[#8b9cb0]'
                        }`}
                      />
                    ) : null}
                    <div>
                      <p className="text-sm font-semibold text-[#e8edf4]">{step.title}</p>
                      <p className="text-xs text-[#8b9cb0]">{step.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {step.status === 'completed' && (
                      <CheckCircleIcon className="h-4 w-4 text-emerald-300" />
                    )}
                    {step.status === 'error' && (
                      <ExclamationTriangleIcon className="h-4 w-4 text-rose-300" />
                    )}
                    <span className="text-[11px] uppercase tracking-[0.14em] text-[#8b9cb0]">
                      Stage {index + 1}/{steps.length}
                    </span>
                  </div>
                </div>
                {step.status === 'processing' && (
                  <div className="mt-2 w-full bg-[#0f1728] rounded-full h-1.5 border border-[rgba(148,163,184,0.14)] overflow-hidden">
                    <div
                      className="h-1.5 rounded-full transition-all duration-300 bg-[linear-gradient(90deg,#22d3ee_0%,#38bdf8_100%)]"
                      style={{ width: `${step.progress}%` }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {footer}
      </div>
    </div>
  );
};

export default FabricCreationProgressModal;
