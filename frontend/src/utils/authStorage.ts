const TOKEN_KEY = 'weave_access_token';
const USER_KEY = 'weave_user';

export type WeaveRole = 'admin' | 'user';

export type WeaveFeatureKey =
  | 'dashboard'
  | 'create_knowledge'
  | 'train_ml'
  | 'fabrics'
  | 'test_llm'
  | 'context'
  | 'ontology'
  | 'ontology_enrichment'
  | 'agent_utilities'
  | 'user_management';

export interface WeaveUser {
  id: string;
  username: string;
  display_name: string;
  role?: WeaveRole;
  allowed_features?: WeaveFeatureKey[];
  is_active?: boolean;
}

export const getStoredToken = (): string | null => localStorage.getItem(TOKEN_KEY);

export const getStoredUser = (): WeaveUser | null => {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as WeaveUser;
  } catch {
    return null;
  }
};

export const storeAuthSession = (token: string, user: WeaveUser): void => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const clearAuthSession = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

export const getAuthHeaders = (): Record<string, string> => {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const userInitials = (user: WeaveUser | null): string => {
  if (!user?.display_name) return '??';
  const parts = user.display_name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
  }
  return (user.display_name.slice(0, 2) || user.username.slice(0, 2)).toUpperCase();
};

export const isAdminUser = (user: WeaveUser | null | undefined): boolean =>
  Boolean(user && user.role === 'admin');

export const userCanAccess = (
  user: WeaveUser | null | undefined,
  feature: WeaveFeatureKey,
): boolean => {
  if (!user) return false;
  if (feature === 'dashboard') return true;
  if (user.role === 'admin') return true;
  return (user.allowed_features || []).includes(feature);
};
