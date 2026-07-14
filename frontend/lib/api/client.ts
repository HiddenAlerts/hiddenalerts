/** REST base, no trailing slash (e.g. https://api.hiddenalerts.com/api). */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'https://api.hiddenalerts.com/api';

export type HttpRequestError = Error & { status: number; body: unknown };

function httpRequestError(status: number, body: unknown): HttpRequestError {
  const err = new Error(`Request failed: ${status}`) as HttpRequestError;
  err.name = 'HttpRequestError';
  err.status = status;
  err.body = body;
  return err;
}

function resolveUrl(path: string) {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const base = API_BASE_URL.replace(/\/$/, '');
  const segment = path.replace(/^\//, '');
  return `${base}/${segment}`;
}

export type ApiRequestInit = RequestInit & {
  json?: Record<string, unknown> | unknown[];
  /**
   * When set, an `Authorization: Bearer <token>` header is added. Used by
   * admin (backend JWT) and subscriber (Supabase access token) callers.
   * Passing `null` is treated as "no token".
   */
  token?: string | null;
};

export async function apiRequest<TResponse>(
  path: string,
  init?: ApiRequestInit,
): Promise<TResponse> {
  const { json, headers: userHeaders, token, ...rest } = init ?? {};
  const url = resolveUrl(path);

  const body =
    json !== undefined
      ? JSON.stringify(json)
      : (rest as { body?: BodyInit | null }).body;

  const headers = new Headers(userHeaders);
  if (json !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(url, { ...rest, body, headers });
  } catch (cause) {
    // Normalize browser network failures so callers always get an Error.message
    // (often "Failed to fetch" — CORS, offline, bad host, or connection reset).
    const message =
      cause instanceof Error && cause.message.trim()
        ? cause.message
        : 'Failed to fetch';
    throw new Error(message, { cause });
  }

  if (res.status === 204) {
    return undefined as TResponse;
  }

  const contentType = res.headers.get('content-type');
  const isJson = contentType?.includes('application/json');

  if (!res.ok) {
    let errBody: unknown;
    if (isJson) {
      try {
        errBody = await res.json();
      } catch {
        errBody = await res.text();
      }
    } else {
      errBody = await res.text();
    }
    throw httpRequestError(res.status, errBody);
  }

  if (isJson) {
    return (await res.json()) as TResponse;
  }
  return (await res.text()) as TResponse;
}

export function apiGet<TResponse>(path: string, init?: ApiRequestInit) {
  return apiRequest<TResponse>(path, { ...init, method: 'GET' });
}

export function apiPost<TResponse>(
  path: string,
  body: NonNullable<ApiRequestInit['json']>,
  init?: ApiRequestInit,
) {
  return apiRequest<TResponse>(path, { ...init, method: 'POST', json: body });
}

export function apiPut<TResponse>(
  path: string,
  body: NonNullable<ApiRequestInit['json']>,
  init?: ApiRequestInit,
) {
  return apiRequest<TResponse>(path, { ...init, method: 'PUT', json: body });
}

export function apiDelete<TResponse>(path: string, init?: ApiRequestInit) {
  return apiRequest<TResponse>(path, { ...init, method: 'DELETE' });
}
