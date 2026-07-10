import React, { useMemo, useState } from 'react';
import JSZip from 'jszip';
import {
  CodeBracketSquareIcon,
  FolderIcon,
  CloudArrowUpIcon,
} from '@heroicons/react/24/outline';
import { getApiUrl } from '../utils/api';
import { getAuthHeaders } from '../utils/authStorage';
import CodebaseFabricProgress from './CodebaseFabricProgress';

interface CodebaseKnowledgeFabricProps {
  onClose: () => void;
  onCreated?: (fabricId: string) => void;
}

type InputTab = 'zip' | 'folder' | 'git';
type AuthMode = 'none' | 'pat' | 'ssh';

const CodebaseKnowledgeFabric: React.FC<CodebaseKnowledgeFabricProps> = ({
  onClose,
  onCreated,
}) => {
  const [tab, setTab] = useState<InputTab>('zip');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [migrationGoal, setMigrationGoal] = useState('');
  const [excludeGlobs, setExcludeGlobs] = useState('node_modules,dist,build,.venv');
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [folderLabel, setFolderLabel] = useState('');
  const [folderZip, setFolderZip] = useState<File | null>(null);
  const [gitUrl, setGitUrl] = useState('');
  const [gitRef, setGitRef] = useState('main');
  const [authMode, setAuthMode] = useState<AuthMode>('none');
  const [pat, setPat] = useState('');
  const [sshKey, setSshKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [progressId, setProgressId] = useState<string | null>(null);
  const [showProgress, setShowProgress] = useState(false);
  const [importing, setImporting] = useState(false);

  const missingRequirements = useMemo(() => {
    const missing: string[] = [];
    if (!name.trim()) missing.push('Fabric name');
    if (tab === 'zip' && !zipFile) missing.push('Zip file');
    if (tab === 'folder' && !folderZip) missing.push('Folder selection');
    if (tab === 'git') {
      if (!gitUrl.trim()) missing.push('Git URL');
      if (authMode === 'pat' && !pat.trim()) missing.push('Personal access token');
      if (authMode === 'ssh' && !sshKey.trim()) missing.push('SSH private key');
    }
    return missing;
  }, [name, tab, zipFile, folderZip, gitUrl, authMode, pat, sshKey]);

  const canSubmit = missingRequirements.length === 0;

  const applyZipFile = (file: File | null) => {
    setZipFile(file);
    setError(null);
    if (file && !name.trim()) {
      const base = file.name.replace(/\.zip$/i, '').replace(/[_-]+/g, ' ').trim();
      if (base) setName(base);
    }
  };

  const handleFolderPick = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);
    try {
      const zip = new JSZip();
      let rootName = 'workspace';
      Array.from(files).forEach((file) => {
        const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
        const parts = rel.split('/');
        if (parts.length > 1) rootName = parts[0];
        zip.file(rel, file);
      });
      setFolderLabel(`${rootName} (${files.length} files)`);
      const blob = await zip.generateAsync({ type: 'blob' });
      setFolderZip(new File([blob], `${rootName}.zip`, { type: 'application/zip' }));
      if (!name.trim()) setName(rootName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to package folder');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) {
      setError(`Please provide: ${missingRequirements.join(', ')}`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('name', name.trim());
      if (description.trim()) form.append('description', description.trim());
      if (migrationGoal.trim()) form.append('migration_goal', migrationGoal.trim());
      if (excludeGlobs.trim()) form.append('exclude_globs', excludeGlobs.trim());

      if (tab === 'git') {
        form.append('mode', 'git');
        form.append('git_url', gitUrl.trim());
        if (gitRef.trim()) form.append('git_ref', gitRef.trim());
        form.append('auth_mode', authMode);
        if (authMode === 'pat') form.append('pat', pat);
        if (authMode === 'ssh') form.append('ssh_private_key', sshKey);
      } else {
        form.append('mode', 'zip');
        const file = tab === 'zip' ? zipFile : folderZip;
        if (!file) throw new Error('Missing zip file');
        form.append('zip_file', file);
      }

      const response = await fetch(getApiUrl('api/v1/knowledge/create-codebase-fabric'), {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: form,
      });
      let payload: any = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      if (!response.ok || payload?.success === false) {
        const detail =
          (typeof payload?.detail === 'string' && payload.detail) ||
          (Array.isArray(payload?.detail) &&
            payload.detail.map((d: any) => d?.msg || JSON.stringify(d)).join('; ')) ||
          payload?.message ||
          `Failed to start codebase fabric (${response.status})`;
        throw new Error(detail);
      }
      const pid = payload?.data?.progress_id as string;
      const fid = payload?.data?.fabric_id as string;
      if (!pid) {
        throw new Error('Backend did not return a progress id. Restart backend and try again.');
      }
      setProgressId(pid);
      setShowProgress(true);
      (window as any).__weave_pending_codebase_fabric = fid;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create codebase fabric');
    } finally {
      setSubmitting(false);
    }
  };

  const handleImportJson = async (file: File | null) => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      if (name.trim()) form.append('name', name.trim());
      const response = await fetch(getApiUrl('api/v1/knowledge/import-codebase-migration'), {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: form,
      });
      const payload = await response.json();
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.detail || payload?.message || 'Import failed');
      }
      const fid = payload?.data?.id as string;
      if (fid && onCreated) onCreated(fid);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  if (showProgress && progressId) {
    return (
      <CodebaseFabricProgress
        progressId={progressId}
        onComplete={() => {
          const fid = (window as any).__weave_pending_codebase_fabric as string | undefined;
          if (fid && onCreated) onCreated(fid);
          setShowProgress(false);
          onClose();
        }}
        onClose={() => {
          setShowProgress(false);
          onClose();
        }}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[rgba(148,163,184,0.16)] bg-[#0b1220] shadow-2xl">
        <div className="flex items-start justify-between border-b border-[rgba(148,163,184,0.12)] px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-[#e8edf4]">Codebase / Workspace Fabric</h2>
            <p className="mt-1 text-sm text-[#8b9cb0]">
              Analyze a zip, folder, or git repo into a knowledge graph and migration JSON.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-xs uppercase tracking-[0.14em] text-[#8b9cb0] hover:text-[#e8edf4]"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 px-6 py-5">
          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[#b7c7da]">Fabric name</span>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#b7c7da]">Migration goal (optional)</span>
              <input
                value={migrationGoal}
                onChange={(e) => setMigrationGoal(e.target.value)}
                placeholder="e.g. Java monolith → Spring Boot services"
                className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
              />
            </label>
          </div>

          <label className="block text-sm">
            <span className="text-[#b7c7da]">Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
            />
          </label>

          <label className="block text-sm">
            <span className="text-[#b7c7da]">Exclude paths (comma-separated)</span>
            <input
              value={excludeGlobs}
              onChange={(e) => setExcludeGlobs(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
            />
          </label>

          <div className="flex flex-wrap gap-2">
            {(
              [
                { id: 'zip' as const, label: 'Upload zip', icon: CloudArrowUpIcon },
                { id: 'folder' as const, label: 'Upload folder', icon: FolderIcon },
                { id: 'git' as const, label: 'Git repository', icon: CodeBracketSquareIcon },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
                  tab === item.id
                    ? 'border-[rgba(94,200,242,0.4)] bg-[rgba(94,200,242,0.14)] text-[#d9f4ff]'
                    : 'border-[rgba(148,163,184,0.16)] text-[#8b9cb0] hover:text-[#e8edf4]'
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </div>

          {tab === 'zip' && (
            <label className="block text-sm">
              <span className="text-[#b7c7da]">Workspace zip</span>
              <input
                type="file"
                accept=".zip,application/zip,application/x-zip-compressed"
                onChange={(e) => applyZipFile(e.target.files?.[0] || null)}
                className="mt-1 block w-full text-sm text-[#b7c7da]"
              />
              {zipFile && (
                <p className="mt-1 text-xs text-[#3ecf9b]">Selected: {zipFile.name}</p>
              )}
            </label>
          )}

          {tab === 'folder' && (
            <label className="block text-sm">
              <span className="text-[#b7c7da]">Select folder</span>
              <input
                type="file"
                // @ts-expect-error webkitdirectory is non-standard but widely supported
                webkitdirectory=""
                directory=""
                multiple
                onChange={(e) => handleFolderPick(e.target.files)}
                className="mt-1 block w-full text-sm text-[#b7c7da]"
              />
              {folderLabel && <p className="mt-1 text-xs text-[#8b9cb0]">Packaged: {folderLabel}</p>}
            </label>
          )}

          {tab === 'git' && (
            <div className="space-y-3 rounded-xl border border-[rgba(148,163,184,0.14)] bg-white/[0.02] p-4">
              <label className="block text-sm">
                <span className="text-[#b7c7da]">Git URL</span>
                <input
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder="https://github.com/org/repo.git or git@github.com:org/repo.git"
                  className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
                />
              </label>
              <label className="block text-sm">
                <span className="text-[#b7c7da]">Branch / tag</span>
                <input
                  value={gitRef}
                  onChange={(e) => setGitRef(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
                />
              </label>
              <div className="flex flex-wrap gap-3 text-sm text-[#b7c7da]">
                {(['none', 'pat', 'ssh'] as AuthMode[]).map((mode) => (
                  <label key={mode} className="inline-flex items-center gap-2">
                    <input
                      type="radio"
                      name="auth"
                      checked={authMode === mode}
                      onChange={() => setAuthMode(mode)}
                    />
                    {mode === 'none' ? 'Public' : mode === 'pat' ? 'PAT' : 'SSH key'}
                  </label>
                ))}
              </div>
              {authMode === 'pat' && (
                <label className="block text-sm">
                  <span className="text-[#b7c7da]">Personal access token</span>
                  <input
                    type="password"
                    value={pat}
                    onChange={(e) => setPat(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4]"
                  />
                </label>
              )}
              {authMode === 'ssh' && (
                <label className="block text-sm">
                  <span className="text-[#b7c7da]">SSH private key</span>
                  <textarea
                    value={sshKey}
                    onChange={(e) => setSshKey(e.target.value)}
                    rows={5}
                    placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                    className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 font-mono text-xs text-[#e8edf4]"
                  />
                </label>
              )}
              <p className="text-[11px] text-[#8b9cb0]">
                Credentials are used only for clone, stored ephemerally for the analysis job, then scrubbed.
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[rgba(148,163,184,0.1)] pt-4">
            <label className="text-xs text-[#8b9cb0]">
              Or import migration JSON:{' '}
              <input
                type="file"
                accept="application/json,.json"
                disabled={importing}
                onChange={(e) => handleImportJson(e.target.files?.[0] || null)}
                className="ml-1 inline text-xs"
              />
            </label>
            <div className="text-right">
              {!canSubmit && (
                <p className="mb-2 text-[11px] text-[#f08984]">
                  Required: {missingRequirements.join(', ')}
                </p>
              )}
              <button
                type="submit"
                disabled={!canSubmit || submitting}
                className="rounded-full border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.16)] px-4 py-2 text-sm font-medium text-[#d9f4ff] hover:bg-[rgba(94,200,242,0.24)] disabled:opacity-50"
              >
                {submitting ? 'Starting…' : 'Analyze & create fabric'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CodebaseKnowledgeFabric;
