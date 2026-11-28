import React, { useEffect, useMemo, useRef, useState } from 'react';
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
  UsersIcon,
} from '@heroicons/react/24/outline';
import WeaveLogo from './WeaveLogo';
import UserAccountBadge from './UserAccountBadge';
import { useAuth } from '../contexts/AuthContext';
import { WeaveFeatureKey } from '../utils/authStorage';

interface LayoutProps {
  children: React.ReactNode;
}

type NavGroup = 'Home' | 'Build' | 'Understand' | 'Use';

const navigation: Array<{
  name: string;
  short: string;
  href: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  sublabel: string;
  feature: WeaveFeatureKey;
  group: NavGroup;
  mobileOnly?: boolean;
}> = [
  { name: 'Dashboard', short: 'Home', href: '/', icon: HomeIcon, sublabel: 'Overview', feature: 'dashboard', group: 'Home' },
  { name: 'Create Knowledge', short: 'Create', href: '/knowledge', icon: BookOpenIcon, sublabel: 'Fabric builder', feature: 'create_knowledge', group: 'Build' },
  { name: 'Available Fabrics', short: 'Fabrics', href: '/fabrics', icon: SparklesIcon, sublabel: 'Catalog and graphs', feature: 'fabrics', group: 'Build' },
  { name: 'Train ML Models', short: 'Train', href: '/train-ml', icon: CpuChipIcon, sublabel: 'Model training', feature: 'train_ml', group: 'Build' },
  { name: 'Ontology Discovery', short: 'Ontology', href: '/ontology', icon: CircleStackIcon, sublabel: 'Schema discovery', feature: 'ontology', group: 'Understand' },
  { name: 'Ontology Enrichment', short: 'Enrich', href: '/ontology/enrichment', icon: BoltIcon, sublabel: 'Governance queue', feature: 'ontology_enrichment', group: 'Understand' },
  { name: 'Context Layer', short: 'Context', href: '/context', icon: MagnifyingGlassIcon, sublabel: 'Fabric → agents', feature: 'context', group: 'Understand' },
  { name: 'Test with LLM', short: 'Ask', href: '/test-llm', icon: ChatBubbleLeftRightIcon, sublabel: 'Ask a fabric', feature: 'test_llm', group: 'Use' },
  // User Management lives in the account badge on desktop so the top bar does not clip "Users" to "Use".
  { name: 'User Management', short: 'Users', href: '/users', icon: UsersIcon, sublabel: 'Platform users', feature: 'user_management', group: 'Use', mobileOnly: true },
];

const GROUP_ORDER: NavGroup[] = ['Home', 'Build', 'Understand', 'Use'];

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const mainRef = useRef<HTMLElement | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();

  const visibleNavigation = useMemo(
    () => navigation.filter((item) => can(item.feature)),
    [can],
  );

  const activeHref = useMemo(() => {
    const matches = visibleNavigation.filter((item) =>
      item.href === '/'
        ? location.pathname === '/'
        : location.pathname === item.href || location.pathname.startsWith(`${item.href}/`),
    );
    if (matches.length === 0) return null;
    return matches.sort((a, b) => b.href.length - a.href.length)[0].href;
  }, [location.pathname, visibleNavigation]);

  const searchItems = visibleNavigation.map((item) => ({
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
    setSidebarOpen(false);
    setSearchOpen(false);
    // Instant scroll reset keeps route changes feeling fluid (no mid-page jump).
    const main = mainRef.current;
    if (main) main.scrollTop = 0;
    else window.scrollTo(0, 0);
    setScrolled(false);
  }, [location.pathname]);

  useEffect(() => {
    const onScroll = () => {
      const y = mainRef.current?.scrollTop ?? window.scrollY ?? 0;
      setScrolled(y > 8);
    };
    onScroll();
    const main = mainRef.current;
    main?.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      main?.removeEventListener('scroll', onScroll);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  return (
    <div className="relative min-h-screen text-[#e8edf4] weave-app-shell">
      {/* Full-bleed atmosphere so wide screens are not empty black gutters */}
      <div className="pointer-events-none fixed inset-0 -z-10 weave-app-atmosphere" aria-hidden />

      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}>
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
        <div className="fixed inset-y-0 left-0 flex w-72 flex-col bg-[#0c121c]/96 backdrop-blur-2xl rounded-r-3xl border-r border-[rgba(148,163,184,0.14)] shadow-2xl shadow-black/40">
          <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-cyan-400/70 via-slate-400/40 to-cyan-500/50 rounded-r" />
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
          <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
            {GROUP_ORDER.map((group) => {
              const items = visibleNavigation.filter((item) => item.group === group);
              if (items.length === 0) return null;
              return (
                <div key={group}>
                  <p className="px-3 pb-1 text-[10px] uppercase tracking-[0.18em] text-[#8b9cb0]">{group}</p>
                  <div className="space-y-1">
                    {items.map((item) => {
                      const active = activeHref === item.href;
                      return (
                        <Link
                          key={item.href}
                          to={item.href}
                          className={`flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm ${
                            active
                              ? 'bg-white/[0.08] text-[#e8edf4] shadow-[inset_0_1px_0_rgba(255,255,255,0.16)]'
                              : 'text-[#9fb0c5] hover:bg-white/[0.04] hover:text-[#e8edf4]'
                          }`}
                          onClick={() => setSidebarOpen(false)}
                        >
                          <item.icon className="h-4 w-4 shrink-0" />
                          <span className="min-w-0">
                            <span className="block truncate">{item.name}</span>
                            <span className="block truncate text-[10px] text-[#8b9cb0]">{item.sublabel}</span>
                          </span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </nav>
          <div className="border-t border-[rgba(148,163,184,0.09)] px-3 py-3">
            <UserAccountBadge />
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="relative z-0 flex h-screen min-h-0 flex-col">
        <header
          className={`weave-topbar fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-5 transition-[padding,background-color] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            scrolled ? 'weave-topbar-scrolled pb-2' : 'pb-0'
          }`}
        >
          <div
            className={`mx-auto flex h-14 max-w-7xl items-center gap-2 rounded-full border px-2.5 transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
              scrolled
                ? 'border-white/16 bg-[#101822]/78 shadow-[0_12px_40px_rgba(0,0,0,0.32),0_0_0_1px_rgba(94,200,242,0.08),inset_0_1px_0_rgba(255,255,255,0.2)] backdrop-blur-2xl'
                : 'border-white/12 bg-[#101822]/72 shadow-[0_18px_50px_rgba(0,0,0,0.22),inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-xl'
            }`}
          >
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-[#cbd5e1] hover:bg-white/[0.06] lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <Bars3Icon className="h-5 w-5" />
            </button>
            <Link to="/" className="flex shrink-0 items-center gap-2 rounded-full px-1.5 py-1">
              <WeaveLogo gradientId="weave-grad-ribbon" className="h-8 w-8" />
              <span className="hidden text-sm font-semibold tracking-[-0.03em] text-[#e8edf4] sm:block">Weave</span>
            </Link>

            <nav className="hidden min-w-0 flex-1 items-center gap-0.5 overflow-x-auto pl-1 pr-3 lg:flex [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {GROUP_ORDER.map((group, groupIndex) => {
                const items = visibleNavigation.filter((item) => item.group === group && !item.mobileOnly);
                if (items.length === 0) return null;
                return (
                  <div key={group} className="flex shrink-0 items-center gap-0.5">
                    {groupIndex > 0 && <span className="mx-1 h-4 w-px bg-white/10" aria-hidden />}
                    {items.map((item) => {
                      const active = activeHref === item.href;
                      return (
                        <Link
                          key={item.href}
                          to={item.href}
                          title={item.name}
                          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1.5 text-[12px] font-medium tracking-[-0.01em] transition ${
                            active
                              ? 'bg-white/[0.1] text-[#e8edf4] shadow-[inset_0_1px_0_rgba(255,255,255,0.28)]'
                              : 'text-[#8b9cb0] hover:bg-white/[0.05] hover:text-[#e8edf4]'
                          }`}
                        >
                          <item.icon className="h-3.5 w-3.5 shrink-0" />
                          <span className="whitespace-nowrap">{item.short}</span>
                        </Link>
                      );
                    })}
                  </div>
                );
              })}
            </nav>

            <div className="relative ml-auto flex shrink-0 items-center gap-2">
              <div className="relative hidden md:block">
                <div className="flex h-9 items-center rounded-full border border-white/10 bg-black/20 px-3 focus-within:border-[rgba(94,200,242,0.4)]">
                  <MagnifyingGlassIcon className="h-3.5 w-3.5 text-[#8b9cb0]" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setSearchOpen(true);
                    }}
                    onFocus={() => setSearchOpen(true)}
                    onBlur={() => setTimeout(() => setSearchOpen(false), 140)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && filteredSearchItems.length > 0) {
                        handleSearchSelect(filteredSearchItems[0].href);
                      }
                      if (e.key === 'Escape') setSearchOpen(false);
                    }}
                    placeholder="Find"
                    aria-label="Find a page"
                    className="ml-2 w-16 bg-transparent text-xs text-[#e8edf4] placeholder:text-[#8b9cb0] focus:w-36 focus:outline-none xl:w-28 xl:focus:w-40 transition-[width]"
                  />
                </div>
                {searchOpen && filteredSearchItems.length > 0 && (
                  <div className="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-white/12 bg-[#0b0f16]/95 shadow-[0_18px_50px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.14)] backdrop-blur-2xl">
                    {filteredSearchItems.slice(0, 8).map((item) => (
                      <button
                        key={item.href}
                        type="button"
                        onMouseDown={() => handleSearchSelect(item.href)}
                        className="block w-full border-b border-white/8 px-3 py-2 text-left last:border-b-0 hover:bg-white/[0.05]"
                      >
                        <span className="block text-xs text-[#e8edf4]">{item.label}</span>
                        <span className="block text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">{item.description}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="hidden sm:block">
                <UserAccountBadge compact />
              </div>
            </div>
          </div>
        </header>

        {/* Page content — top padding clears the fixed menu; scrolls under the soft glass bar */}
        <main
          ref={mainRef}
          className="weave-main-scroll flex-1 overflow-y-auto overflow-x-hidden pt-[4.75rem] pb-3 sm:pt-[5rem] sm:pb-4"
        >
          <div
            key={location.pathname}
            className="kf-page-in mx-auto max-w-7xl px-4 sm:px-6 lg:px-8"
          >
            {children}
          </div>
        </main>

        {/* Bottom status strip */}
        <div className="h-9 border-t border-[rgba(148,163,184,0.1)] bg-[#0d141f]/80 backdrop-blur-2xl px-6">
          <div className="mx-auto flex h-full max-w-7xl items-center justify-between text-[11px]">
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