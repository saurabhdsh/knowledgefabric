import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRightIcon,
  CircleStackIcon,
  DocumentTextIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { ontologyApi } from '../utils/ontologyApi';
import { apiRequest } from '../utils/api';
import { useAuth } from '../contexts/AuthContext';

interface KnowledgeFabric {
  id: string;
  name: string;
  source_type: string;
  status: string;
  model_status?: string;
  document_count: number;
  total_chunks?: number;
  updated_at: string;
}

function tone(fabric: KnowledgeFabric): string {
  if (fabric.status === 'failed' || fabric.model_status === 'failed') return '#f08984';
  if (fabric.status === 'building' || fabric.model_status === 'indexing' || fabric.status === 'training') return '#e8b84a';
  return '#5ec8f2';
}

function activityLabel(item: KnowledgeFabric): string {
  if (item.model_status === 'trained' || item.model_status === 'indexed') return 'Index ready';
  if (item.status === 'building' || item.status === 'training' || item.model_status === 'indexing') return 'Build in progress';
  if (item.status === 'failed') return 'Build failed';
  return 'Fabric updated';
}

const PATHS = [
  {
    to: '/knowledge',
    kicker: '01',
    title: 'Create a fabric',
    copy: 'Bring in a database, a CSV, a PDF, or several sources together.',
  },
  {
    to: '/fabrics',
    kicker: '02',
    title: 'Open the catalog',
    copy: 'Every fabric, its graph, and the evidence on each edge.',
  },
  {
    to: '/ontology',
    kicker: '03',
    title: 'Discover the ontology',
    copy: 'Turn the measured profile into classes, relationships, and a draft.',
  },
  {
    to: '/context',
    kicker: '04',
    title: 'Read the context',
    copy: 'See the packet behind an answer, and where a correction can go.',
  },
];

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fabrics, setFabrics] = useState<KnowledgeFabric[]>([]);
  const [ontologyProjects, setOntologyProjects] = useState(0);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [fabricsResult, projects] = await Promise.all([
          apiRequest('api/v1/knowledge/')
            .then(async (res) => (res.ok ? res.json() : null))
            .catch(() => null),
          ontologyApi.listProjects().catch(() => []),
        ]);

        const fabricsData: KnowledgeFabric[] =
          fabricsResult?.success && Array.isArray(fabricsResult?.data) ? fabricsResult.data : [];

        setFabrics(fabricsData);
        setOntologyProjects(projects.length);

        if (!fabricsResult && projects.length === 0) {
          setError('Load failed. Please check backend server and refresh.');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const totals = useMemo(() => {
    const documents = fabrics.reduce((sum, item) => sum + (item.document_count || 0), 0);
    const chunks = fabrics.reduce((sum, item) => sum + (item.total_chunks || 0), 0);
    const indexed = fabrics.filter((item) => item.model_status === 'trained' || item.model_status === 'indexed').length;
    const active = fabrics.filter((item) => item.status === 'active').length;
    return { documents, chunks, indexed, active };
  }, [fabrics]);

  const loom = useMemo(() => {
    return [...fabrics]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 7);
  }, [fabrics]);

  const recent = loom.slice(0, 5);
  const greeting = user?.display_name || user?.username || 'there';
  const indexReady = totals.indexed > 0;

  const figures = [
    { label: 'Documents', value: totals.documents, note: `${fabrics.length} fabrics` },
    { label: 'Chunks', value: totals.chunks, note: 'Embedded text' },
    { label: 'Indexed', value: totals.indexed, note: `${totals.active} active` },
    { label: 'Ontologies', value: ontologyProjects, note: 'Discovery projects' },
  ];

  return (
    <div className="relative space-y-5 text-[#cbd5e1]">
      <section className="kf-card-in relative overflow-hidden rounded-[28px] border border-white/15 bg-white/[0.05] px-6 py-7 shadow-[0_24px_70px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.2)] backdrop-blur-2xl sm:px-8">
        <div className="pointer-events-none absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent" />
        <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-[#5ec8f2]/10 blur-3xl" />
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-xl">
            <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">Workspace</p>
            <h1 className="mt-2 text-[2rem] font-semibold leading-none tracking-[-0.04em] text-[#e8edf4] sm:text-[2.6rem]">
              {greeting}
            </h1>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-[#9fb0c5]">
              Your fabrics sit on one floor. Open a point to see its graph, the evidence on each edge, and the records behind it.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip
              label="Index"
              value={fabrics.length > 0 ? 'Holding data' : 'Waiting'}
              live={fabrics.length > 0}
            />
            <StatusChip
              label="Embeddings"
              value={indexReady ? 'Ready' : 'Pending'}
              live={indexReady}
            />
            <StatusChip label="API" value={error ? 'Degraded' : 'Running'} live={!error} warn={Boolean(error)} />
            <Link
              to="/knowledge"
              className="inline-flex items-center rounded-full bg-[#f5f5f7] px-4 py-2 text-sm font-semibold text-[#111113] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
            >
              Create fabric
              <ArrowRightIcon className="ml-1.5 h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-2xl border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.12)] px-4 py-3 text-sm text-[#f08984]">
          {error}
        </div>
      )}

      <section className="kf-card-in grid grid-cols-2 overflow-hidden rounded-[28px] border border-white/12 bg-white/[0.04] shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-xl lg:grid-cols-4" style={{ animationDelay: '80ms' }}>
        {figures.map((figure, index) => (
          <div
            key={figure.label}
            className={`px-5 py-4 ${index > 0 ? 'border-white/10 lg:border-l' : ''} ${index > 1 ? 'border-t lg:border-t-0' : ''}`}
          >
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#8b9cb0]">{figure.label}</p>
            <p className="mt-1 text-[1.7rem] font-semibold tabular-nums tracking-[-0.04em] text-[#e8edf4]">
              {loading ? '—' : figure.value.toLocaleString()}
            </p>
            <p className="mt-1 text-[12px] text-[#8b9cb0]">{figure.note}</p>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <section className="kf-card-in relative overflow-hidden rounded-[28px] border border-white/15 bg-[#070b12]/80 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.14)] xl:col-span-8" style={{ animationDelay: '140ms' }}>
          <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/50 to-transparent" />
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">The floor</p>
              <h2 className="mt-1 text-lg font-semibold tracking-[-0.03em] text-[#e8edf4]">Live fabrics</h2>
            </div>
            <Link to="/fabrics" className="text-[12px] text-[#9adfff] hover:text-white">
              All fabrics
            </Link>
          </div>

          <div className="relative mt-2 h-[280px]">
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 280" preserveAspectRatio="none" aria-hidden>
              <path
                className="dash-loom"
                d="M 40 190 C 220 40, 420 250, 640 120 S 900 60, 970 150"
                fill="none"
                stroke="rgba(94,200,242,0.35)"
                strokeWidth="1.2"
              />
            </svg>
            {loading && (
              <p className="absolute left-2 top-4 text-sm text-[#8b9cb0]">Gathering fabrics…</p>
            )}
            {!loading && loom.length === 0 && (
              <Link
                to="/knowledge"
                className="absolute left-1/2 top-1/2 w-44 -translate-x-1/2 -translate-y-1/2 text-center"
              >
                <span className="mx-auto block h-3 w-3 rounded-full border border-[#5ec8f2] bg-[#5ec8f2]/30" />
                <span className="mt-3 block text-sm text-[#e8edf4]">No fabrics yet</span>
                <span className="mt-1 block text-[12px] text-[#8b9cb0]">Create the first one</span>
              </Link>
            )}
            {loom.map((fabric, index) => {
              const t = loom.length === 1 ? 0.5 : index / (loom.length - 1);
              const left = 8 + t * 84;
              const top = 58 - Math.sin(t * Math.PI) * 34;
              return (
                <Link
                  key={fabric.id}
                  to={`/fabrics/${fabric.id}/knowledge-graph`}
                  className="dash-node group absolute w-36 -translate-x-1/2 text-center"
                  style={{ left: `${left}%`, top: `${top}%`, animationDelay: `${120 + index * 70}ms` }}
                >
                  <span
                    className="mx-auto block h-2.5 w-2.5 rounded-full ring-4 ring-[#5ec8f2]/10 transition group-hover:scale-125"
                    style={{ backgroundColor: tone(fabric) }}
                  />
                  <span className="mt-2 block truncate text-[12px] font-medium text-[#e8edf4] group-hover:text-white">
                    {fabric.name}
                  </span>
                  <span className="block truncate text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">
                    {fabric.source_type || 'fabric'}
                  </span>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="kf-card-in rounded-[28px] border border-white/15 bg-white/[0.045] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-xl xl:col-span-4" style={{ animationDelay: '200ms' }}>
          <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">Latest</p>
          <h2 className="mt-1 text-lg font-semibold tracking-[-0.03em] text-[#e8edf4]">What changed</h2>
          <ul className="mt-4 space-y-3">
            {loading && <li className="text-sm text-[#8b9cb0]">Loading activity…</li>}
            {!loading && recent.length === 0 && <li className="text-sm text-[#8b9cb0]">Nothing has moved yet.</li>}
            {recent.map((item) => (
              <li key={item.id}>
                <Link to={`/fabrics/${item.id}/knowledge-graph`} className="block rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2.5 hover:bg-white/[0.06]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[12px] font-medium" style={{ color: tone(item) }}>{activityLabel(item)}</span>
                    <span className="shrink-0 text-[10px] text-[#8b9cb0]">
                      {item.updated_at ? new Date(item.updated_at).toLocaleDateString() : ''}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-sm text-[#e8edf4]">{item.name}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {PATHS.map((path, index) => (
          <Link
            key={path.to}
            to={path.to}
            className="kf-card-in group rounded-[24px] border border-white/12 bg-white/[0.04] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] backdrop-blur-xl transition hover:border-white/25 hover:bg-white/[0.07]"
            style={{ animationDelay: `${260 + index * 70}ms` }}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-[0.2em] text-[#8b9cb0]">{path.kicker}</span>
              <PathIcon index={index} />
            </div>
            <p className="mt-3 text-[15px] font-semibold tracking-[-0.02em] text-[#e8edf4]">{path.title}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-[#8b9cb0]">{path.copy}</p>
          </Link>
        ))}
      </section>
    </div>
  );
};

function StatusChip({ label, value, live, warn }: { label: string; value: string; live: boolean; warn?: boolean }) {
  const dot = warn ? '#f08984' : live ? '#5ec8f2' : '#e8b84a';
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-black/20 px-3 py-1.5 text-[12px] text-[#d5deea]">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: dot }} />
      <span className="text-[#8b9cb0]">{label}</span>
      {value}
    </span>
  );
}

function PathIcon({ index }: { index: number }) {
  const className = 'h-4 w-4 text-[#8b9cb0] group-hover:text-[#9adfff]';
  if (index === 0) return <DocumentTextIcon className={className} />;
  if (index === 1) return <SparklesIcon className={className} />;
  if (index === 2) return <CircleStackIcon className={className} />;
  return <MagnifyingGlassIcon className={className} />;
}

export default Dashboard;
