import React, { useCallback, useEffect, useState } from 'react';
import { CheckIcon, XMarkIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { apiRequest } from '../utils/api';

interface RelationshipCandidate {
  from_table: string;
  from_column?: string;
  from_columns?: string[];
  to_table: string;
  to_column?: string;
  to_columns?: string[];
  overlap?: number;
  confidence?: number;
  status?: string;
  review_reasons?: string[];
  parent_is_sample?: boolean;
  composite?: boolean;
}

interface RelationshipGovernancePanelProps {
  fabricId: string;
}

const RelationshipGovernancePanel: React.FC<RelationshipGovernancePanelProps> = ({ fabricId }) => {
  const [accepted, setAccepted] = useState<RelationshipCandidate[]>([]);
  const [review, setReview] = useState<RelationshipCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiRequest(`api/v1/knowledge/${fabricId}/relationships`);
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.message || 'Could not load relationships');
      }
      setAccepted(data.data?.accepted || []);
      setReview(data.data?.needs_review || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not load relationships');
      setAccepted([]);
      setReview([]);
    } finally {
      setLoading(false);
    }
  }, [fabricId]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (candidate: RelationshipCandidate, decision: 'accept' | 'reject') => {
    setMessage(null);
    setError(null);
    try {
      const res = await apiRequest(`api/v1/knowledge/${fabricId}/relationships/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_table: candidate.from_table,
          from_column: candidate.from_column,
          from_columns: candidate.from_columns,
          to_table: candidate.to_table,
          to_column: candidate.to_column,
          to_columns: candidate.to_columns,
          decision,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.message || 'Review failed');
      }
      setMessage(decision === 'accept' ? 'Relationship accepted for this fabric.' : 'Relationship rejected.');
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Review failed');
    }
  };

  const label = (c: RelationshipCandidate) => {
    const left = c.from_column || (c.from_columns || []).join('+');
    const right = c.to_column || (c.to_columns || []).join('+');
    return `${c.from_table}.${left} → ${c.to_table}.${right}`;
  };

  return (
    <div className="rounded-xl border border-[#243044] bg-[#121820] p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#e8edf4]">Relationship review</h3>
          <p className="mt-1 text-xs text-[#8b9cb0]">
            Keys the profiler is sure about are already in use. Review-band keys wait here until you accept them.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1 rounded-lg border border-[#2a3a4f] px-2.5 py-1.5 text-xs text-[#9adfff] hover:bg-[#1a2433]"
        >
          <ArrowPathIcon className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && <p className="mt-3 text-xs text-rose-300">{error}</p>}
      {message && <p className="mt-3 text-xs text-[#9adfff]">{message}</p>}

      <div className="mt-4 space-y-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-[#6b7c90]">Needs review ({review.length})</p>
          {review.length === 0 ? (
            <p className="mt-2 text-xs text-[#6b7c90]">Nothing waiting.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {review.map((c) => (
                <li key={label(c)} className="rounded-lg border border-[#2a3a4f] bg-[#0d131c] p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm text-[#e8edf4]">{label(c)}</p>
                      <p className="mt-1 text-xs text-[#8b9cb0]">
                        overlap {((c.overlap || 0) * 100).toFixed(0)}%
                        {typeof c.confidence === 'number' ? ` · confidence ${(c.confidence * 100).toFixed(0)}%` : ''}
                        {c.parent_is_sample ? ' · parent is a sample' : ''}
                      </p>
                      {(c.review_reasons || []).slice(0, 2).map((r) => (
                        <p key={r} className="mt-1 text-xs text-[#a8b4c4]">{r}</p>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => decide(c, 'accept')}
                        className="inline-flex items-center gap-1 rounded-lg bg-[#1e3a5f] px-2.5 py-1.5 text-xs text-[#9adfff] hover:bg-[#254a75]"
                      >
                        <CheckIcon className="h-3.5 w-3.5" /> Accept
                      </button>
                      <button
                        type="button"
                        onClick={() => decide(c, 'reject')}
                        className="inline-flex items-center gap-1 rounded-lg border border-[#3a2a2a] px-2.5 py-1.5 text-xs text-rose-200 hover:bg-[#2a1a1a]"
                      >
                        <XMarkIcon className="h-3.5 w-3.5" /> Reject
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-[#6b7c90]">In use ({accepted.length})</p>
          {accepted.length === 0 ? (
            <p className="mt-2 text-xs text-[#6b7c90]">No accepted relationships yet.</p>
          ) : (
            <ul className="mt-2 space-y-1">
              {accepted.slice(0, 12).map((c) => (
                <li key={label(c)} className="text-xs text-[#a8b4c4]">
                  {label(c)}
                  {typeof c.confidence === 'number' ? ` · ${(c.confidence * 100).toFixed(0)}%` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default RelationshipGovernancePanel;
