import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiRequest } from '../utils/api';
import {
  WeaveFeatureKey,
  WeaveUser,
  clearAuthSession,
  getStoredToken,
  getStoredUser,
  isAdminUser,
  storeAuthSession,
  userCanAccess,
} from '../utils/authStorage';

interface AuthContextValue {
  user: WeaveUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAdmin: boolean;
  can: (feature: WeaveFeatureKey) => boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<WeaveUser | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    clearAuthSession();
    setUser(null);
    setToken(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await apiRequest('api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const payload = await response.json();
    if (!response.ok || payload?.success === false) {
      throw new Error(payload?.detail || payload?.error || payload?.message || 'Sign in failed');
    }

    const data = payload.data ?? payload;
    const accessToken = data.access_token as string;
    const nextUser = data.user as WeaveUser;
    storeAuthSession(accessToken, nextUser);
    setToken(accessToken);
    setUser(nextUser);
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      const storedToken = getStoredToken();
      if (!storedToken) {
        setIsLoading(false);
        return;
      }
      try {
        const response = await apiRequest('api/v1/auth/me');
        const payload = await response.json();
        if (!response.ok || payload?.success === false) {
          logout();
        } else {
          const profile = (payload.data ?? payload) as WeaveUser;
          storeAuthSession(storedToken, profile);
          setUser(profile);
          setToken(storedToken);
        }
      } catch {
        logout();
      } finally {
        setIsLoading(false);
      }
    };
    bootstrap();
  }, [logout]);

  const can = useCallback(
    (feature: WeaveFeatureKey) => userCanAccess(user, feature),
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      isLoading,
      isAdmin: isAdminUser(user),
      can,
      login,
      logout,
    }),
    [user, token, isLoading, can, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
};
