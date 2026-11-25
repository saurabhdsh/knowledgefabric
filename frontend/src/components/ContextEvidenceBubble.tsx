import React, { useMemo } from 'react';

export type EvidenceLine = {
  kind: string;
  text: string;
  source_id?: string | null;
  confidence?: number | null;
};

function confidenceLabel(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

/** Highlight claim/member/plan IDs and key=value pairs inside evidence text. */
function highlightEvidence(text: string): React.ReactNode {
  const pattern =
    /(\b(?:CLM|CLL|MBR|PLN|PRV|PAY|EVT)_\w+\b|\b[A-Za-z_][\w.]*\s*=\s*[^\s|;,]+|\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b)/g;
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    const token = match[0];
    const isId = /^(CLM|CLL|MBR|PLN|PRV|PAY|EVT)_/i.test(token);
    const isKv = /=/.test(token);
    parts.push(
      <mark
        key={`h-${key++}`}
        className={`ctx-ev-mark ${isId ? 'is-id' : ''} ${isKv ? 'is-kv' : ''}`}
      >
        {token}
      </mark>
    );
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length ? parts : text;
}

function parseTableLine(text: string): { field?: string; value?: string; raw: string } {
  const m = text.match(/^\s*([A-Za-z0-9_.]+)\s*=\s*(.+?)\s*$/);
  if (!m) return { raw: text };
  return { field: m[1], value: m[2], raw: text };
}

type ContextEvidenceBubbleProps = {
  line: EvidenceLine;
  index?: number;
};

/**
 * Kind-aware evidence bubbles for the Context Layer envelope —
 * TABLE as key chips, PASSAGE as speech bubbles, GRAPH as bond strips.
 */
const ContextEvidenceBubble: React.FC<ContextEvidenceBubbleProps> = ({ line, index = 0 }) => {
  const kind = String(line.kind || 'passage').toLowerCase();
  const conf = line.confidence != null ? Number(line.confidence) : null;
  const confPct = conf != null && !Number.isNaN(conf) ? Math.max(0, Math.min(100, Math.round(conf * 100))) : null;

  const tableParts = useMemo(
    () => (kind === 'table' ? parseTableLine(line.text) : null),
    [kind, line.text]
  );

  const label = kind.toUpperCase();

  return (
    <article
      className={`ctx-ev ctx-ev--${kind}`}
      style={{ animationDelay: `${Math.min(index, 14) * 40}ms` }}
    >
      <div className="ctx-ev__rail" aria-hidden>
        <span className="ctx-ev__badge" title={label}>
          {label}
        </span>
      </div>

      <div className="ctx-ev__body">
        {kind === 'table' && tableParts?.field ? (
          <div className="ctx-ev__kv">
            <span className="ctx-ev__field">{tableParts.field}</span>
            <span className="ctx-ev__eq">=</span>
            <span className="ctx-ev__value">{tableParts.value}</span>
          </div>
        ) : (
          <p className="ctx-ev__text">{highlightEvidence(line.text)}</p>
        )}

        <footer className="ctx-ev__meta">
          <span className="ctx-ev__source" title={line.source_id || undefined}>
            {line.source_id || 'no source'}
          </span>
          {confPct != null && (
            <span className="ctx-ev__conf" title="Evidence confidence">
              <span className="ctx-ev__conf-track" aria-hidden>
                <span className="ctx-ev__conf-fill" style={{ width: `${confPct}%` }} />
              </span>
              <span className="ctx-ev__conf-label">{confidenceLabel(conf)}</span>
            </span>
          )}
        </footer>
      </div>
    </article>
  );
};

export default ContextEvidenceBubble;
