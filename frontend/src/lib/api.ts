import type {
  ActionItem,
  ActionItemWithSession,
  CalendarEventsResponse,
  ChatMessage,
  ExtractedTranscript,
  IntegrationStatus,
  Org,
  Session,
  User,
} from "@/lib/types"

export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include", // send/receive the httpOnly session cookie
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  signup: (body: { email: string; password: string; name?: string }) =>
    request<User>("/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),

  listSessions: () => request<Session[]>("/sessions"),
  createSession: (title?: string) =>
    request<Session>("/sessions", { method: "POST", body: JSON.stringify({ title }) }),
  renameSession: (id: string, title: string) =>
    request<Session>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: "DELETE" }),
  getMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/sessions/${sessionId}/messages`),

  getActions: (sessionId: string) =>
    request<ActionItem[]>(`/sessions/${sessionId}/actions`),
  getAllActions: (status?: string) =>
    request<ActionItemWithSession[]>(
      `/actions${status ? `?status_filter=${encodeURIComponent(status)}` : ""}`
    ),
  updateAction: (id: string, body: Partial<Pick<ActionItem, "status">>) =>
    request<ActionItem>(`/actions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteAction: (id: string) => request<void>(`/actions/${id}`, { method: "DELETE" }),

  getIntegrations: () => request<IntegrationStatus>("/integrations/status"),
  connectIntegration: (toolkit: string) =>
    request<{ url: string }>(`/integrations/${toolkit}/connect`, { method: "POST" }),

  getCalendarEvents: (days = 7) =>
    request<CalendarEventsResponse>(`/calendar/events?days=${days}`),

  getOrg: () => request<Org>("/org"),
  renameOrg: (name: string) =>
    request<Org>("/org", { method: "PATCH", body: JSON.stringify({ name }) }),
  createInvite: (body: { email: string; name?: string }) =>
    request<Org>("/org/invites", { method: "POST", body: JSON.stringify(body) }),
  revokeInvite: (id: string) => request<Org>(`/org/invites/${id}`, { method: "DELETE" }),
  removeMember: (id: string) => request<Org>(`/org/members/${id}`, { method: "DELETE" }),

  extractTranscript: async (file: File): Promise<ExtractedTranscript> => {
    const form = new FormData()
    form.append("file", file)
    const res = await fetch(`${API_BASE}/meetings/extract`, {
      method: "POST",
      credentials: "include",
      body: form, // let the browser set the multipart boundary
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail ?? detail
      } catch {
        /* non-JSON */
      }
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<ExtractedTranscript>
  },
}
