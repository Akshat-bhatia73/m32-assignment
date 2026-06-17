import type { ActionItem, ChatMessage, Session, User } from "@/lib/types"

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
  getMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/sessions/${sessionId}/messages`),

  getActions: (sessionId: string) =>
    request<ActionItem[]>(`/sessions/${sessionId}/actions`),
  updateAction: (id: string, body: Partial<Pick<ActionItem, "status">>) =>
    request<ActionItem>(`/actions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteAction: (id: string) => request<void>(`/actions/${id}`, { method: "DELETE" }),
}
