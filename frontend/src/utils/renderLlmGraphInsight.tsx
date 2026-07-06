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
  },
  light: {
    heading: 'mt-5 border-b border-emerald-200/60 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700/80',
    body: 'text-sm font-normal leading-relaxed text-gray-800',
    paragraph: 'text-sm font-normal leading-relaxed text-gray-800',
    bullet: 'bg-emerald-500/70',
    orderedNum: 'text-gray-500',
    strong: 'font-semibold text-gray-900',
    code: 'rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[13px] text-emerald-800',
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

/**
 * Renders LLM markdown (headings, lists, bold, code) as formatted UI — no raw ## or ** visible.
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
