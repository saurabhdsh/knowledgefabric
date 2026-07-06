import React from 'react';

/** Remove common markdown decorations so nothing reads as raw LLM markup. */
function stripInlineFormatting(s: string): string {
  return s
    .replace(/\*\*([\s\S]*?)\*\*/g, '$1')
    .replace(/__([\s\S]*?)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*([^*\n]+)\*/g, '$1');
}

/**
 * Renders graph insight text as calm editorial UI: no ##, bullets, or backticks visible.
 */
export function renderLlmGraphInsight(raw: string): React.ReactNode {
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
      const title = stripInlineFormatting(heading[2].trim());
      if (!title) continue;
      out.push(
        <h3
          key={`h-${k++}`}
          className="mt-7 border-b border-white/[0.07] pb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
        >
          {title}
        </h3>
      );
      continue;
    }

    if (/^[-*•]\s/.test(trimmed)) {
      const body = stripInlineFormatting(trimmed.replace(/^[-*•]\s+/, ''));
      out.push(
        <div key={`b-${k++}`} className="flex gap-3.5">
          <span
            className="mt-[0.55rem] h-1 w-1 shrink-0 rounded-full bg-violet-400/55"
            aria-hidden
          />
          <p className="min-w-0 flex-1 text-[15px] font-normal leading-[1.68] tracking-[0.02em] text-slate-200/95">
            {body}
          </p>
        </div>
      );
      continue;
    }

    const ordered = trimmed.match(/^(\d+)[.)]\s+(.*)$/);
    if (ordered) {
      const n = ordered[1];
      const body = stripInlineFormatting(ordered[2].trim());
      out.push(
        <div key={`n-${k++}`} className="flex gap-3.5">
          <span className="w-7 shrink-0 pt-[0.12rem] text-right text-[12px] font-medium tabular-nums text-slate-500">
            {n}.
          </span>
          <p className="min-w-0 flex-1 text-[15px] font-normal leading-[1.68] tracking-[0.02em] text-slate-200/95">
            {body}
          </p>
        </div>
      );
      continue;
    }

    out.push(
      <p
        key={`p-${k++}`}
        className="text-[15px] font-normal leading-[1.72] tracking-[0.015em] text-slate-200/[0.93]"
      >
        {stripInlineFormatting(trimmed)}
      </p>
    );
  }

  return (
    <div
      className="insight-editorial font-light [&>h3:first-of-type]:mt-0"
      style={{ fontFeatureSettings: '"kern" 1, "liga" 1, "ss01" 1' }}
    >
      {out}
    </div>
  );
}
