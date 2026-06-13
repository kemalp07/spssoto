const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getApiUrl(): string {
  return API_URL;
}

export async function apiCall<T>(
  endpoint: string,
  body?: unknown,
  options?: { timeout?: number; signal?: AbortSignal; method?: string },
): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = options?.timeout ?? 60_000;
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const signal = options?.signal ?? controller.signal;

  try {
    const method = options?.method ?? (body !== undefined ? 'POST' : 'GET');
    const res = await fetch(`${API_URL}${endpoint}`, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const detail = typeof err.detail === 'string'
        ? err.detail
        : Array.isArray(err.detail)
          ? err.detail.map((d: { msg?: string }) => d.msg || '').join(', ')
          : 'Sunucu hatası';
      throw new ApiError(res.status, detail || 'Sunucu hatası');
    }

    return res.json() as Promise<T>;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function apiUpload<T>(
  endpoint: string,
  formData: FormData,
  options?: { timeout?: number; signal?: AbortSignal },
): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = options?.timeout ?? 120_000;
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      body: formData,
      signal: options?.signal ?? controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, err.detail || 'Sunucu hatası');
    }

    return res.json() as Promise<T>;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function apiBlob(
  endpoint: string,
  body: unknown,
  options?: { timeout?: number },
): Promise<Blob> {
  const controller = new AbortController();
  const timeoutMs = options?.timeout ?? 120_000;
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, err.detail || 'Sunucu hatası');
    }

    return res.blob();
  } finally {
    window.clearTimeout(timeout);
  }
}
