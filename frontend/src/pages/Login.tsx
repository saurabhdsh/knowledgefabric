import React, { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import WeaveLogo from '../components/WeaveLogo';
import { useAuth } from '../contexts/AuthContext';

const Login: React.FC = () => {
  const { login, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState('Saurabh');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/';

  if (!isLoading && isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#040508] text-[#e8edf4] flex items-center justify-center px-4 py-12 relative overflow-hidden">
      <a
        href="/"
        className="absolute top-6 left-6 sm:top-8 sm:left-8 z-20 flex items-center"
        aria-label="TCS"
      >
        <img
          src={`${process.env.PUBLIC_URL || ''}/TCS-logo-white.svg`}
          alt="TCS"
          className="w-48 sm:w-56 md:w-64 h-auto opacity-95"
        />
      </a>

      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-64 w-64 rounded-full bg-cyan-500/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="rounded-3xl border border-[rgba(148,163,184,0.14)] bg-[#080a10]/90 backdrop-blur-2xl shadow-2xl shadow-black/40 overflow-hidden">
          <div className="px-8 pt-10 pb-8 text-center border-b border-[rgba(148,163,184,0.09)]">
            <div className="mx-auto w-16 h-16 mb-4">
              <WeaveLogo gradientId="weave-grad-login" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-[#e8edf4]">Weave</h1>
            <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-[#8b9cb0]">
              Knowledge Fabric Platform
            </p>
            <p className="mt-4 text-sm text-[#8b9cb0]">Sign in to your private workspace</p>
          </div>

          <form onSubmit={handleSubmit} className="px-8 py-8 space-y-5">
            {error && (
              <div className="rounded-xl border border-[rgba(240,137,132,0.35)] bg-[rgba(240,137,132,0.12)] px-4 py-3 text-sm text-[#ffd6d3]">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="username" className="block text-xs font-medium uppercase tracking-[0.16em] text-[#8b9cb0] mb-2">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-xl border border-[rgba(148,163,184,0.18)] bg-[#0d1422]/80 px-4 py-3 text-sm text-[#e8edf4] placeholder:text-[#8b9cb0] focus:outline-none focus:border-[rgba(94,200,242,0.45)] focus:ring-1 focus:ring-[rgba(94,200,242,0.35)]"
                placeholder="Enter your username"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium uppercase tracking-[0.16em] text-[#8b9cb0] mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-[rgba(148,163,184,0.18)] bg-[#0d1422]/80 px-4 py-3 text-sm text-[#e8edf4] placeholder:text-[#8b9cb0] focus:outline-none focus:border-[rgba(94,200,242,0.45)] focus:ring-1 focus:ring-[rgba(94,200,242,0.35)]"
                placeholder="Enter your password"
                required
              />
            </div>

            <button
              type="submit"
              disabled={submitting || isLoading}
              className="w-full rounded-xl border border-[rgba(94,200,242,0.35)] bg-gradient-to-r from-violet-600/80 via-fuchsia-600/70 to-cyan-600/70 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-900/20 transition hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting ? 'Signing in…' : 'Sign in to Weave'}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-[#8b9cb0]">
          Copyright Tata Consultancy Services
        </p>
      </div>
    </div>
  );
};

export default Login;
