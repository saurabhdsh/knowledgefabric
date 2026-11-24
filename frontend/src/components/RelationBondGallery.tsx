import React, { useMemo, useState } from 'react';

export type RelationBond = {
  id?: string;
  source: string;
  label: string;
  target: string;
  meta?: string;
  dimmed?: boolean;
};

type RelationBondGalleryProps = {
  title?: string;
  subtitle?: string;
  bonds: RelationBond[];
  /** Highlight bonds touching this entity label */
  focusEntity?: string | null;
  emptyLabel?: string;
  selectedId?: string | null;
  onBondClick?: (bond: RelationBond) => void;
};

function initials(name: string): string {
  const parts = name.replace(/[_-]+/g, ' ').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
}

function BondArc({
  bond,
  index,
  selected,
  onClick,
}: {
  bond: RelationBond;
  index: number;
  selected?: boolean;
  onClick?: () => void;
}) {
  const safe = String(bond.id ?? index).replace(/[^a-zA-Z0-9_-]/g, '');
  const pathId = `bond-path-${safe}`;
  const gradId = `bond-grad-${safe}`;
  const className = `or-bond ${bond.dimmed ? 'is-dimmed' : ''} ${selected ? 'is-selected' : ''} ${onClick ? 'or-bond--interactive' : ''}`;
  const style = { animationDelay: `${Math.min(index, 12) * 45}ms` };

  const body = (
    <>
      <div className="or-bond__node or-bond__node--source" title={bond.source}>
        <span className="or-bond__orb" aria-hidden>
          {initials(bond.source)}
        </span>
        <span className="or-bond__name">{bond.source}</span>
      </div>

      <div className="or-bond__bridge">
        <svg className="or-bond__svg" viewBox="0 0 220 56" preserveAspectRatio="none">
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(94,200,242,0.15)" />
              <stop offset="50%" stopColor="rgba(94,200,242,0.95)" />
              <stop offset="100%" stopColor="rgba(62,207,155,0.9)" />
            </linearGradient>
          </defs>
          <path
            id={pathId}
            d="M 8 40 C 70 8, 150 8, 212 40"
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth="1.6"
            className="or-bond__arc"
          />
          <circle r="2.4" fill="#5ec8f2" className="or-bond__pulse">
            <animateMotion dur={`${2.8 + (index % 5) * 0.35}s`} repeatCount="indefinite" rotate="auto">
              <mpath href={`#${pathId}`} />
            </animateMotion>
          </circle>
        </svg>
        <div className="or-bond__label" title={bond.label}>
          <span className="or-bond__label-text">{bond.label}</span>
          {bond.meta ? <span className="or-bond__meta">{bond.meta}</span> : null}
        </div>
      </div>

      <div className="or-bond__node or-bond__node--target" title={bond.target}>
        <span className="or-bond__orb or-bond__orb--target" aria-hidden>
          {initials(bond.target)}
        </span>
        <span className="or-bond__name">{bond.target}</span>
      </div>
    </>
  );

  if (onClick) {
    return (
      <button type="button" className={className} style={style} onClick={onClick}>
        {body}
      </button>
    );
  }

  return (
    <article className={className} style={style}>
      {body}
    </article>
  );
}

/**
 * Constellation-style relationship gallery — replaces flat source → label → target rows
 * with orbital bond arcs (Canonical matrix + Graph edge types).
 */
const RelationBondGallery: React.FC<RelationBondGalleryProps> = ({
  title = 'Relationship constellation',
  subtitle = 'Each bond is a typed arc between entities — not a spreadsheet row',
  bonds,
  focusEntity = null,
  emptyLabel = 'No relationships in this result.',
  selectedId = null,
  onBondClick,
}) => {
  const [filter, setFilter] = useState<string | 'all'>('all');

  const sources = useMemo(() => {
    const set = new Set<string>();
    bonds.forEach((b) => {
      if (b.source) set.add(b.source);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [bonds]);

  const visible = useMemo(() => {
    return bonds.map((b) => {
      const focus = focusEntity?.trim();
      const dimmedByFocus = Boolean(
        focus && focus !== b.source && focus !== b.target,
      );
      const dimmedByFilter = filter !== 'all' && b.source !== filter;
      return { ...b, dimmed: dimmedByFocus || dimmedByFilter };
    });
  }, [bonds, focusEntity, filter]);

  if (bonds.length === 0) {
    return <p className="text-sm text-[#8b9cb0]">{emptyLabel}</p>;
  }

  return (
    <div className="or-bond-gallery">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-[#e8edf4] tracking-tight">{title}</h3>
          <p className="text-[12px] text-[#8b9cb0] mt-1 max-w-xl">{subtitle}</p>
        </div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-[#5ec8f2]/80">
          {bonds.length} bond{bonds.length === 1 ? '' : 's'}
        </p>
      </div>

      {sources.length > 1 && (
        <div className="or-bond-filters mb-4">
          <button
            type="button"
            className={`or-bond-chip ${filter === 'all' ? 'is-active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All sources
          </button>
          {sources.map((src) => (
            <button
              key={src}
              type="button"
              className={`or-bond-chip ${filter === src ? 'is-active' : ''}`}
              onClick={() => setFilter(src)}
            >
              From {src}
            </button>
          ))}
        </div>
      )}

      <div className="or-bond-grid">
        {visible.map((bond, i) => (
          <BondArc
            key={bond.id ?? `${bond.source}-${bond.label}-${bond.target}-${i}`}
            bond={bond}
            index={i}
            selected={Boolean(selectedId && bond.id === selectedId)}
            onClick={onBondClick ? () => onBondClick(bond) : undefined}
          />
        ))}
      </div>
    </div>
  );
};

export default RelationBondGallery;
