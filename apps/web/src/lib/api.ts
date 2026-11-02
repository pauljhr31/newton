// Thin client for the NEWTON API. Auth lives in httpOnly cookies set by the API;
// this code never sees or stores tokens.

export type Role = "admin" | "estimator" | "viewer";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrateur",
  estimator: "Chargé d'affaires",
  viewer: "Lecture seule",
};

export interface CompanyBrief {
  id: string;
  name: string;
  role: Role;
  is_demo: boolean;
}

export interface Me {
  user_id: string;
  email: string;
  full_name: string;
  must_change_password: boolean;
  role: Role;
  company: CompanyBrief;
  companies: CompanyBrief[];
}

export interface Company {
  id: string;
  name: string;
  siret: string | null;
  is_demo: boolean;
}

export interface Member {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
}

export interface MemberCreated {
  member: Member;
  existing_account: boolean;
  temporary_password: string | null;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  actor_type: "user" | "ai" | "system";
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let code = "error";
  let message = `Erreur ${res.status}`;
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      code = detail.code;
      message = detail.message;
    } else if (Array.isArray(detail)) {
      code = "validation";
      message = "Certaines valeurs saisies sont invalides.";
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, code, message);
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  refreshing ??= fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "x-newton-csrf": "1" },
    credentials: "same-origin",
  })
    .then((r) => r.ok)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
  retry = true,
): Promise<T> {
  const res = await fetch(path, {
    method: options.method ?? "GET",
    credentials: "same-origin",
    headers: {
      "x-newton-csrf": "1",
      ...(options.body !== undefined ? { "content-type": "application/json" } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  // The access token lives 15 minutes: renew it silently once, then retry.
  if (res.status === 401 && retry && !path.startsWith("/api/auth/")) {
    if (await tryRefresh()) return api<T>(path, options, false);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function loadMe(): Promise<Me | null> {
  try {
    return await api<Me>("/api/auth/me");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && (await tryRefresh())) {
      return api<Me>("/api/auth/me", {}, false).catch(() => null);
    }
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}
