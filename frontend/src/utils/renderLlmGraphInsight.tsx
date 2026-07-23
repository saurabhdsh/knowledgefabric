import React from 'react';

type LlmMarkdownTheme = 'dark' | 'light';

const THEME_STYLES = {
  dark: {
    heading: 'mt-5 border-b border-white/[0.07] pb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400',
    body: 'text-[15px] font-normal leading-[1.68] tracking-[0.02em] text-slate-200/95',
    paragraph: 'text-[15px] font-normal leading-[1.72] tracking-[0.015em] text-slate-200/[0.93]',
    bullet: 'bg-violet-400/55',
    orderedNum: 'text-slate-500',
    strong: 'font-semibold text-slate-100',
    code: 'rounded bg-white/10 px-1.5 py-0.5 font-mono text-[13px] text-cyan-200/90',
    tableWrap: 'my-3 overflow-x-auto rounded-lg border border-white/10',
    table: 'min-w-full border-collapse text-left text-[13px]',
    th: 'border-b border-white/10 bg-white/[0.04] px-3 py-2 font-semibold uppercase tracking-wide text-[10px] text-slate-400',
    td: 'border-b border-white/[0.06] px-3 py-2 text-slate-200/95 tabular-nums',
    trAlt: 'bg-white/[0.02]',
  },
  light: {
    heading: 'mt-5 border-b border-emerald-200/60 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700/80',
    body: 'text-sm font-normal leading-relaxed text-gray-800',
    paragraph: 'text-sm font-normal leading-relaxed text-gray-800',
    bullet: 'bg-emerald-500/70',
    orderedNum: 'text-gray-500',
    strong: 'font-semibold text-gray-900',
    code: 'rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[13px] text-emerald-800',
    tableWrap: 'my-3 overflow-x-auto rounded-lg border border-gray-200',
    table: 'min-w-full border-collapse text-left text-sm',
    th: 'border-b border-gray-200 bg-gray-50 px-3 py-2 font-semibold uppercase tracking-wide text-[10px] text-gray-500',
    td: 'border-b border-gray-100 px-3 py-2 text-gray-800 tabular-nums',
    trAlt: 'bg-gray-50/60',
  },
} as const;

/** Render **bold**, `code`, and *italic* inline without showing raw markdown. */
function renderInlineMarkdown(text: string, theme: LlmMarkdownTheme): React.ReactNode[] {
  const styles = THEME_STYLES[theme];
  const pattern = /(\*\*[\s\S]*?\*\*|__[\s\S]*?__|`[^`\n]+`|\*[^*\n]+\*)/g;
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') || token.startsWith('__')) {
      nodes.push(
        <strong key={`s-${key++}`} className={styles.strong}>
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('`')) {
      nodes.push(
        <code key={`c-${key++}`} className={styles.code}>
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('*')) {
      nodes.push(<em key={`e-${key++}`}>{token.slice(1, -1)}</em>);
    } else {
      nodes.push(token);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes.length > 0 ? nodes : [text];
}

function isTableSeparator(line: string): boolean {
  // | --- | :---: | ---: |
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return false;
  const parts = trimmed
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim());
  if (parts.length === 0) return false;
  return parts.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function splitTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((c) => c.trim());
}

function looksLikeTableRow(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return false;
  if (isTableSeparator(trimmed)) return true;
  // Require at least one pipe with content on both sides or leading/trailing pipes
  return /^\|?.+\|.+\|?$/.test(trimmed) && splitTableRow(trimmed).length >= 2;
}

/**
 * Renders LLM markdown (headings, lists, bold, code, tables) as formatted UI.
 */
export function renderLlmMarkdown(raw: string, theme: LlmMarkdownTheme = 'dark'): React.ReactNode {
  const styles = THEME_STYLES[theme];
  const lines = raw.split(/\r?\n/);
  const out: React.ReactNode[] = [];
  let k = 0;

  const pushSpacer = () => {
    out.push(<div key={`sp-${k++}`} className="h-2.5 shrink-0" aria-hidden />);
  };

  let prevContent = false;
  for (let i = 0; i < lines.length; i += 1) {
    const trimmed = lines[i].trim();
    if (!trimmed) {
      if (prevContent) pushSpacer();
      prevContent = false;
      continue;
    }

    // Markdown table block
    if (looksLikeTableRow(trimmed)) {
      const tableLines: string[] = [];
      let j = i;
      while (j < lines.length && looksLikeTableRow(lines[j].trim())) {
        tableLines.push(lines[j].trim());
        j += 1;
      }
      const dataLines = tableLines.filter((line) => !isTableSeparator(line));
      if (dataLines.length >= 1) {
        const header = splitTableRow(dataLines[0]);
        const body = dataLines.slice(1).map(splitTableRow);
        out.push(
          <div key={`t-${k++}`} className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  {header.map((cell, idx) => (
                    <th key={`th-${idx}`} className={styles.th}>
                      {renderInlineMarkdown(cell, theme)}
                    </th>
                  ))}
                </tr>
              </thead>
              {body.length > 0 && (
                <tbody>
                  {body.map((row, rIdx) => (
                    <tr key={`tr-${rIdx}`} className={rIdx % 2 === 1 ? styles.trAlt : undefined}>
                      {header.map((_, cIdx) => (
                        <td key={`td-${rIdx}-${cIdx}`} className={styles.td}>
                          {renderInlineMarkdown(row[cIdx] ?? '', theme)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              )}
            </table>
          </div>
        );
        prevContent = true;
        i = j - 1;
        continue;
      }
    }

    prevContent = true;

    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const title = heading[2].trim();
      if (!title) continue;
      out.push(
        <h3 key={`h-${k++}`} className={styles.heading}>
          {renderInlineMarkdown(title, theme)}
        </h3>
      );
      continue;
    }

    if (/^[-*•]\s/.test(trimmed)) {
      const body = trimmed.replace(/^[-*•]\s+/, '');
      out.push(
        <div key={`b-${k++}`} className="flex gap-3">
          <span
            className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${styles.bullet}`}
            aria-hidden
          />
          <p className={`min-w-0 flex-1 ${styles.body}`}>{renderInlineMarkdown(body, theme)}</p>
        </div>
      );
      continue;
    }

    const ordered = trimmed.match(/^(\d+)[.)]\s+(.*)$/);
    if (ordered) {
      out.push(
        <div key={`n-${k++}`} className="flex gap-3">
          <span className={`w-6 shrink-0 pt-0.5 text-right text-xs font-medium tabular-nums ${styles.orderedNum}`}>
            {ordered[1]}.
          </span>
          <p className={`min-w-0 flex-1 ${styles.body}`}>{renderInlineMarkdown(ordered[2].trim(), theme)}</p>
        </div>
      );
      continue;
    }

    out.push(
      <p key={`p-${k++}`} className={styles.paragraph}>
        {renderInlineMarkdown(trimmed, theme)}
      </p>
    );
  }

  return (
    <div className="llm-markdown font-light [&>h3:first-of-type]:mt-0" style={{ fontFeatureSettings: '"kern" 1, "liga" 1' }}>
      {out}
    </div>
  );
}

/** @deprecated Use renderLlmMarkdown — kept for graph insight panels. */
export function renderLlmGraphInsight(raw: string): React.ReactNode {
  return renderLlmMarkdown(raw, 'dark');
}
