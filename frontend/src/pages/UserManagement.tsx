import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiRequest } from '../utils/api';
import { useAuth } from '../contexts/AuthContext';
import { WeaveFeatureKey, WeaveRole, WeaveUser } from '../utils/authStorage';

interface FeatureCatalogItem {
  key: WeaveFeatureKey;
  label: string;
  description: string;
  grantable: boolean;
  default_for_user: boolean;
}

interface ManagedUser extends WeaveUser {
  created_at?: string | null;
  updated_at?: string | null;
}

const emptyCreateForm = {
  username: '',
  display_name: '',
  password: '',
  role: 'user' as WeaveRole,
  allowed_features: ['dashboard', 'fabrics'] as WeaveFeatureKey[],
};

const UserManagement: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [features, setFeatures] = useState<FeatureCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    display_name: '',
    password: '',
    role: 'user' as WeaveRole,
    allowed_features: [] as WeaveFeatureKey[],
    is_active: true,
  });

  const grantableFeatures = useMemo(
    () => features.filter((f) => f.grantable),
    [features],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersRes, featuresRes] = await Promise.all([
        apiRequest('api/v1/users'),
        apiRequest('api/v1/users/features'),
      ]);
      const usersPayload = await usersRes.json();
      const featuresPayload = await featuresRes.json();
      if (!usersRes.ok || usersPayload?.success === false) {
        throw new Error(usersPayload?.detail || usersPayload?.message || 'Failed to load users');
      }
      if (!featuresRes.ok || featuresPayload?.success === false) {
        throw new Error(featuresPayload?.detail || featuresPayload?.message || 'Failed to load features');
      }
      setUsers(usersPayload.data?.users || []);
      setFeatures(featuresPayload.data?.features || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load user management');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggleFeature = (
    list: WeaveFeatureKey[],
    key: WeaveFeatureKey,
    checked: boolean,
  ): WeaveFeatureKey[] => {
    if (checked) {
      return list.includes(key) ? list : [...list, key];
    }
    return list.filter((item) => item !== key);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const body = {
        username: createForm.username.trim(),
        display_name: createForm.display_name.trim() || createForm.username.trim(),
        password: createForm.password,
        role: createForm.role,
        allowed_features:
          createForm.role === 'admin' ? undefined : createForm.allowed_features,
      };
      const response = await apiRequest('api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.detail || payload?.message || 'Failed to create user');
      }
      setSuccess(`Created user ${body.username}`);
      setCreateForm({
        ...emptyCreateForm,
        allowed_features: grantableFeatures
          .filter((f) => f.default_for_user)
          .map((f) => f.key),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (u: ManagedUser) => {
    setEditingId(u.id);
    setEditForm({
      display_name: u.display_name,
      password: '',
      role: (u.role as WeaveRole) || 'user',
      allowed_features: (u.allowed_features || []).filter(
        (k) => k !== 'user_management',
      ) as WeaveFeatureKey[],
      is_active: u.is_active !== false,
    });
    setSuccess(null);
    setError(null);
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const body: Record<string, unknown> = {
        display_name: editForm.display_name.trim(),
        role: editForm.role,
        is_active: editForm.is_active,
        allowed_features:
          editForm.role === 'admin' ? undefined : editForm.allowed_features,
      };
      if (editForm.password.trim()) {
        body.password = editForm.password;
      }
      const response = await apiRequest(`api/v1/users/${editingId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.detail || payload?.message || 'Failed to update user');
      }
      setSuccess('User updated');
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (u: ManagedUser) => {
    if (u.id === currentUser?.id) {
      setError('You cannot delete your own account.');
      return;
    }
    const confirmed = window.confirm(
      `Delete user "${u.username}"? This cannot be undone.`,
    );
    if (!confirmed) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    // Optimistic remove so the table updates immediately
    const previousUsers = users;
    setUsers((prev) => prev.filter((row) => row.id !== u.id));
    if (editingId === u.id) {
      setEditingId(null);
    }
    try {
      const response = await apiRequest(`api/v1/users/${u.id}/delete`, {
        method: 'POST',
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
          payload?.message ||
          `Failed to delete user (${response.status})`;
        throw new Error(detail);
      }
      setSuccess(`Deleted user ${u.username}`);
      await load();
    } catch (err) {
      setUsers(previousUsers);
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setSaving(false);
    }
  };

  const featureLabel = (key: string) =>
    features.find((f) => f.key === key)?.label || key;

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-[#8b9cb0]">
        Loading users…
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-[#e8edf4] tracking-tight">User Management</h1>
        <p className="mt-1 text-sm text-[#8b9cb0]">
          Create platform users and choose which features normal users can access. Only admins can manage users.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          {success}
        </div>
      )}

      <section className="rounded-2xl border border-[rgba(148,163,184,0.14)] bg-[#0b1220]/70 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#8b9cb0]">
          Create user
        </h2>
        <form onSubmit={handleCreate} className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm">
            <span className="text-[#b7c7da]">Username</span>
            <input
              required
              value={createForm.username}
              onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#b7c7da]">Display name</span>
            <input
              required
              value={createForm.display_name}
              onChange={(e) => setCreateForm((f) => ({ ...f, display_name: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#b7c7da]">Password</span>
            <input
              required
              type="password"
              minLength={6}
              value={createForm.password}
              onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#b7c7da]">Role</span>
            <select
              value={createForm.role}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, role: e.target.value as WeaveRole }))
              }
              className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
            >
              <option value="user">Normal user</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          {createForm.role === 'admin' ? (
            <div className="md:col-span-2 rounded-xl border border-[rgba(94,200,242,0.2)] bg-[rgba(94,200,242,0.08)] px-4 py-3 text-sm text-[#d9f4ff]">
              Admins have full access to all platform features, including User Management.
            </div>
          ) : (
            <div className="md:col-span-2">
              <div className="text-sm text-[#b7c7da] mb-2">Features this user can use</div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {grantableFeatures.map((feature) => {
                  const checked = createForm.allowed_features.includes(feature.key);
                  return (
                    <label
                      key={feature.key}
                      className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-sm cursor-pointer ${
                        checked
                          ? 'border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.1)]'
                          : 'border-[rgba(148,163,184,0.14)] bg-white/[0.02]'
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={checked}
                        onChange={(e) =>
                          setCreateForm((f) => ({
                            ...f,
                            allowed_features: toggleFeature(
                              f.allowed_features,
                              feature.key,
                              e.target.checked,
                            ),
                          }))
                        }
                      />
                      <span>
                        <span className="block text-[#e8edf4]">{feature.label}</span>
                        <span className="block text-[11px] text-[#8b9cb0]">{feature.description}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-full border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.16)] px-4 py-2 text-sm font-medium text-[#d9f4ff] hover:bg-[rgba(94,200,242,0.24)] disabled:opacity-50"
            >
              {saving ? 'Creating…' : 'Create user'}
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-[rgba(148,163,184,0.14)] bg-[#0b1220]/70 overflow-hidden">
        <div className="px-5 py-4 border-b border-[rgba(148,163,184,0.1)]">
          <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#8b9cb0]">
            Platform users
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-[0.14em] text-[#8b9cb0]">
              <tr className="border-b border-[rgba(148,163,184,0.1)]">
                <th className="px-5 py-3 font-medium">User</th>
                <th className="px-5 py-3 font-medium">Role</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Features</th>
                <th className="px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-[rgba(148,163,184,0.08)] align-top">
                  <td className="px-5 py-3">
                    <div className="text-[#e8edf4] font-medium">{u.display_name}</div>
                    <div className="text-[11px] text-[#8b9cb0]">{u.username}</div>
                    {u.id === currentUser?.id && (
                      <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-cyan-300">
                        You
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-[#b7c7da] capitalize">{u.role || 'user'}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] ${
                        u.is_active !== false
                          ? 'bg-emerald-500/15 text-emerald-200'
                          : 'bg-red-500/15 text-red-200'
                      }`}
                    >
                      {u.is_active !== false ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-[#8b9cb0] max-w-md">
                    {u.role === 'admin'
                      ? 'Full access'
                      : (u.allowed_features || [])
                          .filter((k) => k !== 'user_management')
                          .map(featureLabel)
                          .join(', ') || 'None'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => startEdit(u)}
                        className="text-[11px] uppercase tracking-[0.12em] text-[#5ec8f2] hover:text-[#d9f4ff]"
                      >
                        Edit
                      </button>
                      {u.id !== currentUser?.id && (
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => handleDelete(u)}
                          className="text-[11px] uppercase tracking-[0.12em] text-red-300 hover:text-red-100 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {editingId && (
        <section className="rounded-2xl border border-[rgba(94,200,242,0.25)] bg-[#0b1220]/90 p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#8b9cb0]">
              Edit user
            </h2>
            <button
              type="button"
              onClick={() => setEditingId(null)}
              className="text-[11px] uppercase tracking-[0.12em] text-[#8b9cb0] hover:text-[#e8edf4]"
            >
              Cancel
            </button>
          </div>
          <form onSubmit={handleUpdate} className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[#b7c7da]">Display name</span>
              <input
                required
                value={editForm.display_name}
                onChange={(e) => setEditForm((f) => ({ ...f, display_name: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#b7c7da]">New password (optional)</span>
              <input
                type="password"
                minLength={6}
                value={editForm.password}
                onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#b7c7da]">Role</span>
              <select
                value={editForm.role}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, role: e.target.value as WeaveRole }))
                }
                className="mt-1 w-full rounded-lg border border-[rgba(148,163,184,0.2)] bg-[#080a10] px-3 py-2 text-[#e8edf4] focus:outline-none focus:border-[rgba(94,200,242,0.45)]"
              >
                <option value="user">Normal user</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-[#b7c7da] mt-6">
              <input
                type="checkbox"
                checked={editForm.is_active}
                onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
              />
              Active account
            </label>

            {editForm.role === 'admin' ? (
              <div className="md:col-span-2 rounded-xl border border-[rgba(94,200,242,0.2)] bg-[rgba(94,200,242,0.08)] px-4 py-3 text-sm text-[#d9f4ff]">
                Admins have full access to all platform features.
              </div>
            ) : (
              <div className="md:col-span-2">
                <div className="text-sm text-[#b7c7da] mb-2">Features this user can use</div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {grantableFeatures.map((feature) => {
                    const checked = editForm.allowed_features.includes(feature.key);
                    return (
                      <label
                        key={feature.key}
                        className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-sm cursor-pointer ${
                          checked
                            ? 'border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.1)]'
                            : 'border-[rgba(148,163,184,0.14)] bg-white/[0.02]'
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={checked}
                          onChange={(e) =>
                            setEditForm((f) => ({
                              ...f,
                              allowed_features: toggleFeature(
                                f.allowed_features,
                                feature.key,
                                e.target.checked,
                              ),
                            }))
                          }
                        />
                        <span>
                          <span className="block text-[#e8edf4]">{feature.label}</span>
                          <span className="block text-[11px] text-[#8b9cb0]">{feature.description}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={saving}
                className="rounded-full border border-[rgba(94,200,242,0.35)] bg-[rgba(94,200,242,0.16)] px-4 py-2 text-sm font-medium text-[#d9f4ff] hover:bg-[rgba(94,200,242,0.24)] disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
};

export default UserManagement;
