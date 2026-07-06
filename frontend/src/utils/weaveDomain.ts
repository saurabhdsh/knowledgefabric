export type WeaveDomain = 'generic' | 'pharma';

const STORAGE_KEY = 'weave_domain';

export function getWeaveDomain(): WeaveDomain {
  try {
    const v = sessionStorage.getItem(STORAGE_KEY);
    if (v === 'pharma' || v === 'generic') return v;
  } catch {
    /* ignore */
  }
  return 'generic';
}

export function setWeaveDomain(domain: WeaveDomain): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, domain);
  } catch {
    /* ignore */
  }
}
