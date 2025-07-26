import React from 'react';
import {
  DocumentTextIcon,
  MagnifyingGlassIcon,
  CpuChipIcon,
  ServerIcon,
  ChartBarIcon,
  ClockIcon,
  CloudArrowUpIcon,
} from '@heroicons/react/24/outline';

const Dashboard: React.FC = () => {
  // Mock data - in real app this would come from API
  const stats = [
    { name: 'Total Documents', value: '1,234', icon: DocumentTextIcon, change: '+12%', changeType: 'positive' },
    { name: 'Knowledge Sources', value: '45', icon: ServerIcon, change: '+3', changeType: 'positive' },
    { name: 'Search Queries', value: '892', icon: MagnifyingGlassIcon, change: '+23%', changeType: 'positive' },
    { name: 'Model Accuracy', value: '94.2%', icon: CpuChipIcon, change: '+2.1%', changeType: 'positive' },
  ];

  const recentActivity = [
    { id: 1, action: 'PDF uploaded', document: 'technical_manual.pdf', time: '2 minutes ago' },
    { id: 2, action: 'Database connected', document: 'customer_data', time: '15 minutes ago' },
    { id: 3, action: 'Model training completed', document: 'knowledge_fabric_v2', time: '1 hour ago' },
    { id: 4, action: 'Search performed', document: 'API documentation', time: '2 hours ago' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Welcome to your Knowledge Fabric. Monitor your knowledge base and system performance.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((item) => (
          <div key={item.name} className="card">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <item.icon className="h-8 w-8 text-primary-600" />
              </div>
              <div className="ml-4 flex-1">
                <p className="text-sm font-medium text-gray-500">{item.name}</p>
                <p className="text-2xl font-semibold text-gray-900">{item.value}</p>
              </div>
            </div>
            <div className="mt-4">
              <span className={`inline-flex items-baseline px-2.5 py-0.5 rounded-full text-xs font-medium ${
                item.changeType === 'positive' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {item.change}
              </span>
              <span className="ml-2 text-sm text-gray-500">from last month</span>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
          <div className="space-y-3">
            <button className="w-full btn-primary flex items-center justify-center">
              <DocumentTextIcon className="h-5 w-5 mr-2" />
              Create Knowledge Fabric
            </button>
            <button className="w-full btn-secondary flex items-center justify-center">
              <CpuChipIcon className="h-5 w-5 mr-2" />
              Train Model
            </button>
            <button className="w-full btn-secondary flex items-center justify-center">
              <ServerIcon className="h-5 w-5 mr-2" />
              Manage Database
            </button>
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-4">
            {recentActivity.map((activity) => (
              <div key={activity.id} className="flex items-center space-x-3">
                <div className="flex-shrink-0">
                  <ClockIcon className="h-5 w-5 text-gray-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{activity.action}</p>
                  <p className="text-sm text-gray-500">{activity.document}</p>
                </div>
                <div className="flex-shrink-0">
                  <p className="text-sm text-gray-500">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">System Status</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="h-3 w-3 bg-green-400 rounded-full"></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-900">Vector Database</p>
              <p className="text-sm text-gray-500">Online</p>
            </div>
          </div>
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="h-3 w-3 bg-green-400 rounded-full"></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-900">BERT Model</p>
              <p className="text-sm text-gray-500">Active</p>
            </div>
          </div>
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="h-3 w-3 bg-green-400 rounded-full"></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-900">API Server</p>
              <p className="text-sm text-gray-500">Running</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard; 