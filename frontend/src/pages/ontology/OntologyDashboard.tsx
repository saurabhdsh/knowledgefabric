import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  CircleStackIcon,
  PlusIcon,
  FolderIcon,
  ArrowRightIcon,
  DocumentTextIcon,
  ChartBarIcon,
  TrashIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { ontologyApi, OntologyProject, KnowledgeFabricLite } from '../../utils/ontologyApi';
import { getWeaveDomain, setWeaveDomain, type WeaveDomain } from '../../utils/weaveDomain';
import PharmaOntologyDiscovery from './PharmaOntologyDiscovery';

const OntologyDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [weaveDomain, setWeaveDomainState] = useState<WeaveDomain>(() => getWeaveDomain());
  const [projects, setProjects] = useState<OntologyProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [fabrics, setFabrics] = useState<KnowledgeFabricLite[]>([]);
  const [selectedFabricId, setSelectedFabricId] = useState('');
  const [creatingFromFabric, setCreatingFromFabric] = useState(false);

  useEffect(() => {
    Promise.all([
      ontologyApi.listProjects().then(setProjects).catch(() => setProjects([])),
      ontologyApi.listKnowledgeFabrics().then((data) => {
        setFabrics(data);
        if (data.length > 0) setSelectedFabricId(data[0].id);
      }).catch(() => setFabrics([])),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setWeaveDomain(weaveDomain);
  }, [weaveDomain]);


  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createName.trim()) return;
    setCreating(true);
    try {
      const proj = await ontologyApi.createProject(createName.trim(), createDesc.trim() || undefined);
      setProjects(prev => [...prev, proj]);
      setCreateName('');
      setCreateDesc('');
      navigate(`/ontology/workspace/${proj.id}`);
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const handleCreateFromFabric = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFabricId) return;
    setCreatingFromFabric(true);
    try {
      const fabric = fabrics.find(f => f.id === selectedFabricId);
      const proj = await ontologyApi.createProjectFromFabric(
        selectedFabricId,
        fabric ? `${fabric.name} Ontology` : undefined,
        fabric ? `Ontology project created from Knowledge Fabric '${fabric.name}'.` : undefined
      );
      setProjects(prev => [...prev, proj]);
      navigate(`/ontology/workspace/${proj.id}?source=fabric`);
    } catch (err) {
      console.error(err);
      window.alert(err instanceof Error ? err.message : 'Failed to create project from knowledge fabric');
    } finally {
      setCreatingFromFabric(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, projectId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm('Delete this project? Its versions and runs will be removed.')) return;
    setDeletingId(projectId);
    try {
      await ontologyApi.deleteProject(projectId);
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } catch (err) {
      console.error(err);
      window.alert(err instanceof Error ? err.message : 'Failed to delete project');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-8 text-[#cbd5e1] [&_.bg-white]:bg-[#10141d]/75 [&_.bg-gray-50]:bg-white/[0.03] [&_.bg-gray-100]:bg-white/[0.05] [&_.bg-teal-50]:bg-[rgba(94,200,242,0.08)] [&_.border-teal-200]:border-[rgba(94,200,242,0.25)] [&_.text-teal-800]:text-[#5ec8f2] [&_.text-teal-700]:text-[#cbd5e1] [&_.text-teal-500]:text-[#5ec8f2] [&_.text-gray-900]:text-[#e8edf4] [&_.text-gray-800]:text-[#cbd5e1] [&_.text-gray-700]:text-[#cbd5e1] [&_.text-gray-600]:text-[#8b9cb0] [&_.text-gray-500]:text-[#8b9cb0] [&_.text-gray-400]:text-[#8b9cb0] [&_.border-gray-200]:border-[rgba(148,163,184,0.11)] [&_.border-gray-300]:border-[rgba(148,163,184,0.2)] [&_.hover\:bg-gray-50:hover]:bg-white/[0.06] [&_input]:bg-[#10141d]/70 [&_input]:text-[#e8edf4] [&_input]:border-[rgba(148,163,184,0.2)] [&_input]:placeholder:text-[#8b9cb0]">
      <div>
        <h1 className="text-2xl font-bold text-[#e8edf4] flex items-center gap-2">
          <CircleStackIcon className="w-8 h-8 text-[#5ec8f2]" />
          Ontology Discovery
        </h1>
        <p className="mt-1 text-gray-600">
          Ingest PDF, Word (DOCX), XML, and images; extract entities, relationships, and attributes; then review and export a domain ontology.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] p-1">
            <button
              type="button"
              onClick={() => setWeaveDomainState('generic')}
              className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                weaveDomain === 'generic'
                  ? 'bg-[rgba(94,200,242,0.18)] text-[#e8edf4]'
                  : 'text-[#8b9cb0]'
              }`}
            >
              Generic discovery
            </button>
            <button
              type="button"
              onClick={() => setWeaveDomainState('pharma')}
              className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                weaveDomain === 'pharma'
                  ? 'bg-[rgba(167,139,250,0.22)] text-[#e8edf4]'
                  : 'text-[#8b9cb0]'
              }`}
            >
              Pharma Drug Manufacturing
            </button>
          </div>
          <nav className="flex flex-wrap items-center gap-2 text-xs text-[#8b9cb0]" aria-label="Weave journey">
            <Link to="/knowledge" className="hover:text-[#5ec8f2]">
              Create Fabric
            </Link>
            <span aria-hidden>→</span>
            <Link to="/fabrics" className="hover:text-[#5ec8f2]">
              View Graph
            </Link>
            <span aria-hidden>→</span>
            <span className="text-[#5ec8f2]">Discover</span>
            <span aria-hidden>→</span>
            <Link to="/ontology/enrichment" className="hover:text-[#5ec8f2]">
              Enrich
            </Link>
          </nav>
          <button
            type="button"
            onClick={() => navigate('/ontology/enrichment')}
            className="inline-flex items-center px-3 py-1.5 rounded-lg border border-[rgba(94,200,242,0.32)] bg-[rgba(94,200,242,0.12)] text-[#5ec8f2] text-sm"
          >
            Open Ontology Enrichment Queue
          </button>
        </div>
      </div>

      {weaveDomain === 'pharma' && <PharmaOntologyDiscovery />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Create project</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={createName}
                onChange={e => setCreateName(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:ring-teal-500"
                placeholder="e.g. Claims Domain"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Description (optional)</label>
              <input
                type="text"
                value={createDesc}
                onChange={e => setCreateDesc(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-teal-500 focus:ring-teal-500"
                placeholder="Brief description"
              />
            </div>
            <button
              type="submit"
              disabled={creating || !createName.trim()}
              className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium text-[#e8edf4] border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30 hover:from-[#5ec8f2]/40 hover:to-[#9b8bd4]/40 disabled:opacity-50"
            >
              <PlusIcon className="w-4 h-4 mr-2" />
              Create project
            </button>
          </form>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Projects</h2>
          {loading ? (
            <p className="text-gray-500">Loading…</p>
          ) : projects.length === 0 ? (
            <p className="text-gray-500">No projects yet. Create one to start.</p>
          ) : (
            <ul className="space-y-2">
              {projects.map(p => (
                <li key={p.id}>
                  <div className="flex items-center gap-2 rounded-lg border border-gray-200 overflow-hidden hover:bg-gray-50">
                    <button
                      type="button"
                      onClick={() => navigate(`/ontology/workspace/${p.id}`)}
                      className="flex-1 flex items-center justify-between px-4 py-3 text-left min-w-0"
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <FolderIcon className="w-5 h-5 text-[#5ec8f2] shrink-0" />
                        <span className="truncate">{p.name}</span>
                      </span>
                      <ArrowRightIcon className="w-4 h-4 text-gray-400 shrink-0 ml-2" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, p.id)}
                      disabled={deletingId === p.id}
                      className="p-2 text-[#8b9cb0] hover:text-[#f08984] hover:bg-white/[0.05] disabled:opacity-50"
                      title="Delete project"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <SparklesIcon className="w-5 h-5 text-[#5ec8f2]" />
          Create Ontology from Existing Knowledge Fabric
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Select an existing Knowledge Fabric as source. This creates an Ontology Discovery project pre-linked by source context.
        </p>
        <form onSubmit={handleCreateFromFabric} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700">Knowledge Fabric</label>
            <select
              value={selectedFabricId}
              onChange={e => setSelectedFabricId(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm bg-[#10141d]/70 text-[#e8edf4]"
            >
              {fabrics.length === 0 && <option value="">No fabrics available</option>}
              {fabrics.map(f => (
                <option key={f.id} value={f.id}>
                  {f.name} {f.source_type ? `(${f.source_type})` : ''}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={creatingFromFabric || !selectedFabricId}
            className="inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium text-[#e8edf4] border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30 hover:from-[#5ec8f2]/40 hover:to-[#9b8bd4]/40 disabled:opacity-50"
          >
            {creatingFromFabric ? 'Creating...' : 'Create from Fabric'}
          </button>
        </form>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">Workflow</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-sm text-gray-600">
          <div className="rounded-lg border border-[rgba(94,200,242,0.25)] bg-[rgba(94,200,242,0.08)] p-4">
            <p className="text-sm font-semibold text-gray-900 mb-2">Path A: Create from Source Artifacts</p>
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <DocumentTextIcon className="w-5 h-5 text-teal-500" />
                Create/Open project
              </li>
              <li className="flex items-center gap-2">
                <DocumentTextIcon className="w-5 h-5 text-teal-500" />
                Upload PDF, DOCX, XML, or images in <strong>Source Artifacts</strong>
              </li>
              <li className="flex items-center gap-2">
                <ChartBarIcon className="w-5 h-5 text-teal-500" />
                Run discovery and review ontology outputs
              </li>
              <li className="flex items-center gap-2">
                <CircleStackIcon className="w-5 h-5 text-teal-500" />
                Approve and export JSON, CSV, or graph schema
              </li>
            </ul>
          </div>
          <div className="rounded-lg border border-[rgba(155,139,212,0.3)] bg-[rgba(155,139,212,0.1)] p-4">
            <p className="text-sm font-semibold text-gray-900 mb-2">Path B: Create from Existing Knowledge Fabric</p>
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <SparklesIcon className="w-5 h-5 text-[#9b8bd4]" />
                Select fabric and click <strong>Create from Fabric</strong>
              </li>
              <li className="flex items-center gap-2">
                <CircleStackIcon className="w-5 h-5 text-[#9b8bd4]" />
                Workspace opens as <strong>fabric-linked</strong>
              </li>
              <li className="flex items-center gap-2">
                <DocumentTextIcon className="w-5 h-5 text-[#9b8bd4]" />
                <strong>No Source Artifacts upload required</strong>
              </li>
              <li className="flex items-center gap-2">
                <ChartBarIcon className="w-5 h-5 text-[#9b8bd4]" />
                Review versions/discovery history and continue ontology refinement
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OntologyDashboard;
