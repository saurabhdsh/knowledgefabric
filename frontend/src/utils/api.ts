// API utility functions
// Use explicit backend URL to avoid depending on dev-server proxy.

import { getAuthHeaders } from './authStorage';

export const getApiUrl = (endpoint: string): string => {
  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  return `${API_BASE_URL}/${cleanEndpoint}`;
};

export const apiRequest = async (endpoint: string, options: RequestInit = {}): Promise<Response> => {
  const url = getApiUrl(endpoint);
  const headers = new Headers(options.headers ?? {});
  Object.entries(getAuthHeaders()).forEach(([key, value]) => headers.set(key, value));
  return fetch(url, { ...options, headers });
};

/** Authenticated fetch for legacy call sites that build their own URL. */
export const authenticatedFetch = (url: string, options: RequestInit = {}): Promise<Response> => {
  const headers = new Headers(options.headers ?? {});
  Object.entries(getAuthHeaders()).forEach(([key, value]) => headers.set(key, value));
  return fetch(url, { ...options, headers });
};
