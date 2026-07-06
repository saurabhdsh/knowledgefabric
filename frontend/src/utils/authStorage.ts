const TOKEN_KEY = 'weave_access_token';
const USER_KEY = 'weave_user';

export interface WeaveUser {
  id: string;
  username: string;
  display_name: string;
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
