import React, { useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  HomeIcon,
  BookOpenIcon,
  Bars3Icon,
  XMarkIcon,
  SparklesIcon,
  ChatBubbleLeftRightIcon,
  MagnifyingGlassIcon,
  CpuChipIcon,
  CircleStackIcon,
  BoltIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';
import { useState } from 'react';
import WeaveLogo from './WeaveLogo';
import UserAccountBadge from './UserAccountBadge';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { 
    name: 'Dashboard', 
    href: '/', 
    icon: HomeIcon,
    sublabel: 'Overview',
    color: 'from-blue-500 to-blue-600',
    bgColor: 'bg-blue-50',
    textColor: 'text-blue-700',
    iconColor: 'text-blue-500'
  },
  { 
    name: 'Create Knowledge', 
    href: '/knowledge', 
    icon: BookOpenIcon,
    sublabel: 'Fabric Builder',
    color: 'from-purple-500 to-purple-600',
    bgColor: 'bg-purple-50',
    textColor: 'text-purple-700',
    iconColor: 'text-purple-500'
  },
  { 
    name: 'Train ML Models', 
    href: '/train-ml', 
    icon: CpuChipIcon,
    sublabel: 'Model Training',
    color: 'from-red-500 to-red-600',
    bgColor: 'bg-red-50',
    textColor: 'text-red-700',
    iconColor: 'text-red-500'
  },
  { 
    name: 'Available Fabrics', 
    href: '/fabrics', 
    icon: SparklesIcon,
    sublabel: 'Fabric Catalog',
    color: 'from-indigo-500 to-indigo-600',
    bgColor: 'bg-indigo-50',
    textColor: 'text-indigo-700',
    iconColor: 'text-indigo-500'
  },
  { 
    name: 'Test with LLM', 
    href: '/test-llm', 
    icon: ChatBubbleLeftRightIcon,
    sublabel: 'Agent Testing',
    color: 'from-emerald-500 to-emerald-600',
    bgColor: 'bg-emerald-50',
    textColor: 'text-emerald-700',
    iconColor: 'text-emerald-500'
  },
  { 
    name: 'Context Analysis', 
    href: '/context', 
    icon: MagnifyingGlassIcon,
    sublabel: 'Semantic Insights',
    color: 'from-orange-500 to-orange-600',
    bgColor: 'bg-orange-50',
    textColor: 'text-orange-700',
    iconColor: 'text-orange-500'
  },
  { 
    name: 'Ontology Discovery', 
    href: '/ontology', 
    icon: CircleStackIcon,
    sublabel: 'Schema Explorer',
    color: 'from-teal-500 to-teal-600',
    bgColor: 'bg-teal-50',
    textColor: 'text-teal-700',
    iconColor: 'text-teal-500'
  },
  {
    name: 'Ontology Enrichment',
    href: '/ontology/enrichment',
    icon: BoltIcon,
    sublabel: 'AI Governance Queue',
    color: 'from-cyan-500 to-cyan-600',
    bgColor: 'bg-cyan-50',
    textColor: 'text-cyan-700',
    iconColor: 'text-cyan-500'
  },
  {
    name: 'Agent Data Utilities',
    href: '/ontology/agent-utilities',
    icon: CommandLineIcon,
    sublabel: 'Agent ToolKit',
    color: 'from-violet-500 to-violet-600',
    bgColor: 'bg-violet-50',
    textColor: 'text-violet-700',
    iconColor: 'text-violet-500'
  },
];

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [hoveredMenuHref, setHoveredMenuHref] = useState<string | null>(null);
  const [pinnedMenuHref, setPinnedMenuHref] = useState<string>('/');
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (href: string) =>
    location.pathname === href || (href !== '/' && location.pathname.startsWith(href));

  const searchItems = navigation.map((item) => ({
    label: item.name,
    description: item.sublabel,
    href: item.href,
  }));

  const filteredSearchItems = searchQuery.trim()
    ? searchItems.filter((item) => {
        const q = searchQuery.toLowerCase();
        return item.label.toLowerCase().includes(q) || item.description.toLowerCase().includes(q) || item.href.toLowerCase().includes(q);
      })
    : searchItems.slice(0, 6);

  const handleSearchSelect = (href: string) => {
    navigate(href);
    setSearchQuery('');
    setSearchOpen(false);
  };

  useEffect(() => {
    const matched = navigation.find((item) => isActive(item.href));
    if (matched) {
      setPinnedMenuHref(matched.href);
    }
    // Keep pinned menu aligned with current route after page refresh/direct route entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-[#040508] text-[#e8edf4]">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}>
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
        <div className="fixed inset-y-0 left-0 flex w-72 flex-col bg-[#080a10]/95 backdrop-blur-2xl rounded-r-3xl border-r border-[rgba(148,163,184,0.11)] shadow-2xl shadow-black/40">
          <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-violet-500/80 via-fuchsia-500/50 to-cyan-500/80 rounded-r" />
          <div className="flex h-20 items-center justify-between px-5 border-b border-[rgba(148,163,184,0.09)]">
            <div className="flex items-center gap-3">
              <WeaveLogo gradientId="weave-grad-mobile" className="w-11 h-11" />
              <div>
                <h1 className="text-lg font-semibold text-[#e8edf4] tracking-tight">Weave</h1>
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#8b9cb0]">Knowledge Fabric Platform</p>
              </div>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-2 rounded-xl text-[#8b9cb0] hover:text-[#e8edf4] hover:bg-white/10 transition-colors duration-200"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          <nav className="flex-1 overflow-y-auto px-3 py-5 space-y-1">
            {navigation.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`group flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-2xl transition-all duration-300 ease-out ${
                    active
                      ? 'text-[#e8edf4] border border-[rgba(94,200,242,0.32)] bg-[rgba(94,200,242,0.14)] shadow-[0_0_0_1px_rgba(94,200,242,0.2)]'
                      : 'text-[#8b9cb0] hover:text-[#cbd5e1] hover:bg-white/[0.04] active:scale-[0.98]'
                  }`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <div
                    className={`flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-300 ${
                      active ? 'bg-[rgba(94,200,242,0.2)]' : 'bg-white/[0.03] group-hover:bg-white/[0.06]'
                    }`}
                  >
                    <item.icon className="h-5 w-5 shrink-0" />
                  </div>
                  <span className="truncate">{item.name}</span>
                </Link>
              );
            })}
          </nav>
          <div className="border-t border-[rgba(148,163,184,0.09)] px-3 py-3">
            <UserAccountBadge />
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex min-h-screen flex-col">
        {/* Mobile header */}
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-[rgba(148,163,184,0.09)] bg-[#080a10]/90 backdrop-blur-2xl px-4 sm:gap-x-6 sm:px-6 lg:hidden">
          <button
            type="button"
            className="-m-2.5 p-2.5 text-[#cbd5e1] rounded-xl hover:bg-white/10 transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Bars3Icon className="h-6 w-6" />
          </button>
          <div className="flex flex-1 items-center gap-2 min-w-0">
            <WeaveLogo gradientId="weave-grad-header" className="w-9 h-9" />
            <div className="min-w-0">
              <h1 className="text-base font-semibold text-[#e8edf4] tracking-tight">Weave</h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-[#8b9cb0]">Knowledge Fabric Platform</p>
            </div>
          </div>
          <UserAccountBadge compact />
        </div>

        {/* Desktop compact ribbon */}
        <div className="hidden lg:grid sticky top-0 z-40 h-16 grid-cols-[1fr_auto_1fr] items-center gap-4 px-5 border-b border-[rgba(148,163,184,0.1)] bg-[#080a10]/85 backdrop-blur-2xl">
          <div className="flex items-center justify-between gap-3 w-full">
            <div className="flex items-center gap-3 shrink-0">
              <WeaveLogo gradientId="weave-grad-ribbon" className="w-9 h-9" />
              <div>
                <h1 className="text-sm font-semibold text-[#e8edf4] tracking-tight leading-none">Weave</h1>
                <p className="text-[9px] uppercase tracking-[0.16em] text-[#8b9cb0] mt-1">Knowledge Fabric</p>
              </div>
            </div>
            <div className="hidden xl:flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => navigate('/knowledge')}
                className="inline-flex items-center gap-1 rounded-full border border-[rgba(94,200,242,0.32)] bg-[rgba(94,200,242,0.12)] px-2.5 py-1 text-[11px] font-medium text-[#d9f4ff] hover:bg-[rgba(94,200,242,0.2)]"
              >
                <BookOpenIcon className="h-3.5 w-3.5" />
                New Fabric
              </button>
              <button
                type="button"
                onClick={() => navigate('/fabrics')}
                className="inline-flex items-center gap-1 rounded-full border border-[rgba(148,163,184,0.2)] bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-[#b7c7da] hover:bg-white/[0.08]"
              >
                <SparklesIcon className="h-3.5 w-3.5" />
                Catalog
              </button>
            </div>
          </div>

          <nav className="overflow-hidden justify-self-center">
            <div className="flex items-center justify-center gap-1">
              {navigation.map((item) => {
                const active = isActive(item.href);
                const showLabel = hoveredMenuHref === item.href || pinnedMenuHref === item.href;
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onMouseEnter={() => setHoveredMenuHref(item.href)}
                    onMouseLeave={() => setHoveredMenuHref(null)}
                    onClick={() => setPinnedMenuHref(item.href)}
                    className={`group inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-medium transition-all duration-200 ${
                      active
                        ? 'text-[#e8edf4] border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.16)]'
                        : 'text-[#9fb0c5] border-[rgba(148,163,184,0.14)] bg-white/[0.02] hover:text-[#d9e4f2] hover:border-[rgba(94,200,242,0.28)] hover:bg-white/[0.05]'
                    }`}
                  >
                    <item.icon className="h-3.5 w-3.5" />
                    <span
                      className={`overflow-hidden whitespace-nowrap transition-all duration-300 ease-out ${
                        showLabel ? 'max-w-[180px] opacity-100 ml-0.5' : 'max-w-0 opacity-0'
                      }`}
                    >
                      {item.name}
                    </span>
                  </Link>
                );
              })}
            </div>
          </nav>

          <div className="w-full justify-self-end">
            <div className="flex items-center justify-end gap-2">
              <div className="hidden xl:flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => navigate('/test-llm')}
                  className="inline-flex items-center gap-1 rounded-full border border-[rgba(62,207,155,0.28)] bg-[rgba(62,207,155,0.1)] px-2.5 py-1 text-[11px] font-medium text-[#c9f9e6] hover:bg-[rgba(62,207,155,0.16)]"
                >
                  <ChatBubbleLeftRightIcon className="h-3.5 w-3.5" />
                  Test LLM
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/context')}
                  className="inline-flex items-center gap-1 rounded-full border border-[rgba(251,146,60,0.28)] bg-[rgba(251,146,60,0.1)] px-2.5 py-1 text-[11px] font-medium text-[#ffe2c2] hover:bg-[rgba(251,146,60,0.16)]"
                >
                  <MagnifyingGlassIcon className="h-3.5 w-3.5" />
                  Context
                </button>
              </div>
              <div className="w-full max-w-xs relative hidden 2xl:block">
                <div className="flex items-center rounded-lg border border-[rgba(148,163,184,0.16)] bg-[#0d1422]/70 px-3 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] hover:border-[rgba(94,200,242,0.32)] focus-within:border-[rgba(94,200,242,0.4)]">
                  <MagnifyingGlassIcon className="h-3.5 w-3.5 text-[#5ec8f2]" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setSearchOpen(true);
                    }}
                    onFocus={() => setSearchOpen(true)}
                    onBlur={() => setTimeout(() => setSearchOpen(false), 120)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && filteredSearchItems.length > 0) {
                        handleSearchSelect(filteredSearchItems[0].href);
                      }
                    }}
                    placeholder="Search fabrics, models, and routes..."
                    className="ml-2 w-full bg-transparent text-xs text-[#e8edf4] placeholder:text-[#8b9cb0] focus:outline-none"
                  />
                </div>
                {searchOpen && filteredSearchItems.length > 0 && (
                  <div className="absolute left-0 right-0 mt-1 rounded-lg border border-[rgba(148,163,184,0.18)] bg-[#0b1220]/95 backdrop-blur-xl shadow-2xl z-50 overflow-hidden">
                    {filteredSearchItems.slice(0, 8).map((item) => (
                      <button
                        key={item.href}
                        type="button"
                        onClick={() => handleSearchSelect(item.href)}
                        className="w-full text-left px-3 py-2 hover:bg-white/[0.06] border-b border-[rgba(148,163,184,0.08)] last:border-b-0"
                      >
                        <div className="text-xs text-[#e8edf4]">{item.label}</div>
                        <div className="text-[10px] text-[#8b9cb0] uppercase tracking-[0.14em]">{item.description}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <UserAccountBadge />
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto py-6 lg:py-8">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>

        {/* Bottom status strip */}
        <div className="h-9 border-t border-[rgba(148,163,184,0.09)] bg-[#080a10]/85 backdrop-blur-2xl px-6">
          <div className="flex h-full items-center justify-between text-[11px]">
            <div className="flex items-center gap-2 text-[#e8edf4]">
              <span className="h-2 w-2 rounded-full bg-[#3ecf9b]" />
              <span>System online</span>
              <span className="text-[#8b9cb0]">syncing knowledge index</span>
            </div>
            <div className="hidden sm:block text-[#8b9cb0]">Low latency mode</div>
            <div className="font-mono text-[#8b9cb0]">v0.1.0</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Layout; 