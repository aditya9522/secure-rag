export type QueryMode = "grounded" | "conversational" | "refused";

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  role: "owner" | "admin" | "member";
  groups: string[];
  classification_max: "public" | "internal" | "confidential" | "restricted";
}

export interface UserSummary {
  id: string;
  email: string;
  full_name: string;
  is_system_admin: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserSummary;
  current_organization: OrganizationSummary;
  organizations: OrganizationSummary[];
}

export interface QueryResponse {
  answer: string;
  conversation_id: string | null;
  citations: Array<{
    document_id: string;
    document_title: string;
    chunk_id: string;
    score: number;
  }>;
  grounded: boolean;
  refused: boolean;
  mode: QueryMode;
  policy_flags: string[];
}

export interface DocumentSummary {
  id: string;
  title: string;
  classification: string;
  allowed_groups: string[];
  source_uri: string | null;
  status: string;
  chunks_indexed: number;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
  can_retry?: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageResponse {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode: QueryMode;
  citations: QueryResponse["citations"];
  created_at: string;
}

export interface MemberSummary {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
  groups: string[];
  classification_max: string;
  created_at: string;
}

export type MemberRole = "admin" | "member" | "suspended";
export type Classification = "public" | "internal" | "confidential" | "restricted";

export interface AdminMetrics {
  users: number;
  organizations: number;
  documents: number;
  audit_events_today: number;
}

export interface OrganizationCreationResponse {
  organization: OrganizationSummary;
  owner: UserSummary;
}

export interface NotificationResponse {
  id: string;
  event_type: string;
  title: string;
  detail: string;
  severity: "info" | "success" | "warning";
  created_at: string;
}

export interface ReadinessResponse { status: "ready"; timestamp: number; }

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
let accessToken: string | null = null;
let sessionExpiredHandler: (() => void) | null = null;
let refreshPromise: Promise<AuthResponse> | null = null;

// Keep access tokens out of browser storage. Production deployments should
// prefer the credentialed HttpOnly refresh-cookie/BFF path.
export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function onSessionExpired(handler: (() => void) | null) {
  sessionExpiredHandler = handler;
}

async function requestJson<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  if (!apiBaseUrl) throw new Error("API is not configured. Set VITE_API_BASE_URL.");
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    if (response.status === 401 && retry && path !== "/auth/refresh" && accessToken) {
      try {
        await refreshSession();
        return requestJson<T>(path, init, false);
      } catch {
        accessToken = null;
        sessionExpiredHandler?.();
        throw new Error("Your session has expired. Sign in again.");
      }
    }
    if (response.status === 401) throw new Error("Your session has expired. Sign in again.");
    if (response.status === 403) throw new Error("You do not have access to this workspace.");
    const error = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(error?.detail ?? "The request could not be completed.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(payload: { email: string; password: string }) {
  const result = await requestJson<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
  setAccessToken(result.access_token);
  return result;
}

export async function acceptInvitation(payload: { invitation_token: string; password: string }) {
  const result = await requestJson<AuthResponse>("/auth/accept-invite", { method: "POST", body: JSON.stringify(payload) });
  setAccessToken(result.access_token);
  return result;
}

export async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = requestJson<AuthResponse>("/auth/refresh", { method: "POST" }, false)
      .then((result) => {
        setAccessToken(result.access_token);
        return result;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function logout() {
  await requestJson<void>("/auth/logout", { method: "POST" });
  setAccessToken(null);
}

export async function queryWorkspace(query: string, conversationId?: string): Promise<QueryResponse | null> {
  if (!apiBaseUrl) return null;
  return requestJson<QueryResponse>("/v1/query", {
    method: "POST",
    body: JSON.stringify({ query, conversation_id: conversationId }),
  });
}

export async function streamQueryWorkspace(
  query: string,
  conversationId: string | undefined,
  onDelta: (content: string) => void,
  signal?: AbortSignal,
  retry = true,
): Promise<QueryResponse | null> {
  if (!apiBaseUrl) return null;
  const headers = new Headers({ "Content-Type": "application/json", Accept: "text/event-stream" });
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${apiBaseUrl}/v1/query/stream`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({ query, conversation_id: conversationId }),
    signal,
  });
  if (response.status === 401 && retry && accessToken) {
    try {
      await refreshSession();
      return streamQueryWorkspace(query, conversationId, onDelta, signal, false);
    } catch {
      accessToken = null;
      sessionExpiredHandler?.();
      throw new Error("Your session has expired. Sign in again.");
    }
  }
  if (!response.ok) {
    if (response.status === 401) throw new Error("Your session has expired. Sign in again.");
    if (response.status === 403) throw new Error("You do not have access to this workspace.");
    const error = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(error?.detail ?? "The request could not be completed.");
  }
  if (!response.body) throw new Error("The assistant stream is unavailable.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: QueryResponse | null = null;
  const consumeFrame = (frame: string) => {
    const event = frame.match(/^event:\s*(\w+)/m)?.[1] ?? "message";
    const data = frame.match(/^data:\s*(.+)$/m)?.[1];
    if (!data) return;
    const payload = JSON.parse(data) as { content?: string; response?: QueryResponse; detail?: string };
    if (event === "delta" && payload.content) onDelta(payload.content);
    if (event === "complete" && payload.response) completed = payload.response;
    if (event === "error") throw new Error(payload.detail ?? "The assistant is temporarily unavailable.");
  };
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    frames.forEach(consumeFrame);
    if (done) break;
  }
  if (buffer.trim()) consumeFrame(buffer);
  if (!completed) throw new Error("The assistant did not return a complete response.");
  return completed;
}

export function getMe() { return requestJson<{ user: UserSummary; current_organization: OrganizationSummary; organizations: OrganizationSummary[] }>("/v1/me"); }
export function updateMe(payload: { full_name?: string; current_password?: string; new_password?: string }) {
  return requestJson<{ user: UserSummary; current_organization: OrganizationSummary; organizations: OrganizationSummary[] }>("/v1/me", { method: "PATCH", body: JSON.stringify(payload) });
}
export async function switchOrganization(organizationId: string) {
  const result = await requestJson<AuthResponse>("/v1/organizations/switch", { method: "POST", body: JSON.stringify({ organization_id: organizationId }) });
  setAccessToken(result.access_token);
  return result;
}
export function listDocuments(limit = 100, offset = 0) { return requestJson<DocumentSummary[]>(`/v1/documents?limit=${limit}&offset=${offset}`); }
export function revokeDocument(documentId: string) { return requestJson<void>(`/v1/documents/${documentId}`, { method: "DELETE" }); }
export function createConversation() { return requestJson<ConversationSummary>("/v1/conversations", { method: "POST" }); }
export function listConversations(limit = 100, offset = 0) { return requestJson<ConversationSummary[]>(`/v1/conversations?limit=${limit}&offset=${offset}`); }
export function listMessages(conversationId: string, limit = 100, offset = 0) { return requestJson<ChatMessageResponse[]>(`/v1/conversations/${conversationId}/messages?limit=${limit}&offset=${offset}`); }
export function listMembers(limit = 100, offset = 0) { return requestJson<MemberSummary[]>(`/v1/organizations/members?limit=${limit}&offset=${offset}`); }
export function updateMember(memberId: string, payload: { role: MemberRole; groups: string[]; classification_max: Classification }) { return requestJson<{ status: string }>(`/v1/organizations/members/${memberId}`, { method: "PATCH", body: JSON.stringify(payload) }); }
export function inviteMember(payload: { email: string; full_name: string; role: "admin" | "member"; groups: string[]; classification_max: Classification }) { return requestJson<{ invitation_id: string; invitation_token: string; expires_at: string }>("/v1/organizations/invitations", { method: "POST", body: JSON.stringify(payload) }); }
export function uploadDocument(file: File, options: { classification: string; allowed_groups: string[]; source_uri?: string; retryDocumentId?: string }) {
  const body = new FormData();
  body.append("file", file);
  body.append("classification", options.classification);
  body.append("allowed_groups", options.allowed_groups.join(","));
  if (options.source_uri) body.append("source_uri", options.source_uri);
  if (options.retryDocumentId) body.append("retry_document_id", options.retryDocumentId);
  return requestJson<{ document_id: string; chunks_indexed: number }>("/v1/documents", { method: "POST", body });
}
export function getAdminMetrics() { return requestJson<AdminMetrics>("/v1/admin/metrics"); }
export function createOrganization(payload: { name: string; owner_email: string; owner_full_name: string; owner_password: string }) {
  return requestJson<OrganizationCreationResponse>("/v1/admin/organizations", { method: "POST", body: JSON.stringify(payload) });
}
export function listAudit(limit = 100) { return requestJson<Record<string, unknown>[]>(`/v1/admin/audit?limit=${limit}`); }
export function getReadiness() { return requestJson<ReadinessResponse>("/readyz"); }
export function listNotifications(limit = 20) { return requestJson<NotificationResponse[]>(`/v1/notifications?limit=${limit}`); }
