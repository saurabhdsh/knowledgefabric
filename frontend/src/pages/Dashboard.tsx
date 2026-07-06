import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  DocumentTextIcon,
  MagnifyingGlassIcon,
  CpuChipIcon,
  ServerIcon,
  ClockIcon,
  CircleStackIcon,
} from '@heroicons/react/24/outline';
import { ontologyApi } from '../utils/ontologyApi';
import { apiRequest } from '../utils/api';

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

const Dashboard: React.FC = () => {
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

        // Show lightweight warning only if both sources fail to load.
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

  const stats = useMemo(() => {
    const totalDocs = fabrics.reduce((sum, item) => sum + (item.document_count || 0), 0);
    const totalChunks = fabrics.reduce((sum, item) => sum + (item.total_chunks || 0), 0);
    const trainedModels = fabrics.filter((item) => item.model_status === 'trained').length;
    const activeFabrics = fabrics.filter((item) => item.status === 'active').length;

    return [
      { name: 'Total Documents', value: totalDocs.toLocaleString(), icon: DocumentTextIcon, helper: `${fabrics.length} fabrics indexed` },
      { name: 'Total Chunks', value: totalChunks.toLocaleString(), icon: CircleStackIcon, helper: 'Vectorized text chunks' },
      { name: 'Trained Models', value: trainedModels.toLocaleString(), icon: CpuChipIcon, helper: `${activeFabrics} active fabrics` },
      { name: 'Ontology Projects', value: ontologyProjects.toLocaleString(), icon: MagnifyingGlassIcon, helper: 'Discovery workspaces' },
    ];
  }, [fabrics, ontologyProjects]);

  const recentActivity = useMemo(() => {
    return [...fabrics]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 5)
      .map((item, index) => ({
        id: `${item.id}-${index}`,
        action: item.model_status === 'trained' ? 'Model ready' : item.status === 'training' ? 'Training in progress' : 'Fabric updated',
        document: item.name,
        time: new Date(item.updated_at).toLocaleString(),
      }));
  }, [fabrics]);

  return (
    <div className="space-y-6 text-[#cbd5e1]">
      {/* Header */}
      <div>
        <p className="text-[10px] uppercase tracking-[0.2em] text-[#8b9cb0]">Command Center</p>
        <h1 className="text-2xl font-bold text-[#e8edf4]">Dashboard</h1>
        <p className="mt-1 text-sm text-[#8b9cb0]">
          Welcome to your Knowledge Fabric. Monitor your knowledge base and system performance.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.12)] px-4 py-3 text-sm text-[#f08984]">
          {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((item) => (
          <div key={item.name} className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-5 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <item.icon className="h-8 w-8 text-[#5ec8f2]" />
              </div>
              <div className="ml-4 flex-1">
                <p className="text-sm font-medium text-[#8b9cb0]">{item.name}</p>
                <p className="text-2xl font-semibold text-[#e8edf4]">{loading ? '...' : item.value}</p>
              </div>
            </div>
            <div className="mt-4">
              <span className="text-sm text-[#8b9cb0]">{item.helper}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-6 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <h3 className="text-lg font-medium text-[#e8edf4] mb-4">Quick Actions</h3>
          <div className="space-y-3">
            <Link to="/knowledge" className="w-full rounded-lg border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30 text-[#e8edf4] py-2.5 px-4 font-medium flex items-center justify-center hover:from-[#5ec8f2]/40 hover:to-[#9b8bd4]/40 transition-colors">
              <DocumentTextIcon className="h-5 w-5 mr-2" />
              Create Knowledge Fabric
            </Link>
            <Link to="/train-ml" className="w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#cbd5e1] py-2.5 px-4 font-medium flex items-center justify-center hover:bg-white/[0.06] transition-colors">
              <CpuChipIcon className="h-5 w-5 mr-2" />
              Train Model
            </Link>
            <Link to="/fabrics" className="w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-white/[0.03] text-[#cbd5e1] py-2.5 px-4 font-medium flex items-center justify-center hover:bg-white/[0.06] transition-colors">
              <ServerIcon className="h-5 w-5 mr-2" />
              Manage Fabrics
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-6 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <h3 className="text-lg font-medium text-[#e8edf4] mb-4">Recent Activity</h3>
          <div className="space-y-4">
            {loading && <p className="text-sm text-[#8b9cb0]">Loading activity...</p>}
            {!loading && recentActivity.length === 0 && <p className="text-sm text-[#8b9cb0]">No activity yet.</p>}
            {recentActivity.map((activity) => (
              <div key={activity.id} className="flex items-center space-x-3">
                <div className="flex-shrink-0">
                  <ClockIcon className="h-5 w-5 text-[#8b9cb0]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#e8edf4]">{activity.action}</p>
                  <p className="text-sm text-[#8b9cb0]">{activity.document}</p>
                </div>
                <div className="flex-shrink-0">
                  <p className="text-xs text-[#8b9cb0]">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="rounded-2xl border border-[rgba(148,163,184,0.11)] bg-[#10141d]/75 p-6 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
        <h3 className="text-lg font-medium text-[#e8edf4] mb-4">System Status</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className={`h-3 w-3 rounded-full ${fabrics.length > 0 ? 'bg-[#3ecf9b]' : 'bg-[#e8b84a]'}`}></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-[#e8edf4]">Vector Database</p>
              <p className="text-sm text-[#8b9cb0]">{fabrics.length > 0 ? 'Online' : 'Awaiting data'}</p>
            </div>
          </div>
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className={`h-3 w-3 rounded-full ${fabrics.some(f => f.model_status === 'trained') ? 'bg-[#3ecf9b]' : 'bg-[#e8b84a]'}`}></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-[#e8edf4]">BERT Model</p>
              <p className="text-sm text-[#8b9cb0]">{fabrics.some(f => f.model_status === 'trained') ? 'Active' : 'Training pending'}</p>
            </div>
          </div>
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className={`h-3 w-3 rounded-full ${error ? 'bg-[#f08984]' : 'bg-[#3ecf9b]'}`}></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-[#e8edf4]">API Server</p>
              <p className="text-sm text-[#8b9cb0]">{error ? 'Degraded' : 'Running'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard; 