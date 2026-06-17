export type User = {
  id: string
  email: string
  name: string | null
}

export type Session = {
  id: string
  title: string
  created_at: string
}

export type ChatMessage = {
  id: string
  role: "user" | "assistant" | "tool"
  content: string
  created_at: string
}

export type ActionStatus = "open" | "scheduled" | "sent" | "done"

export type ActionItem = {
  id: string
  session_id: string
  task: string
  owner: string | null
  due_date: string | null
  status: ActionStatus
  external_ref: string | null
  created_at: string
  updated_at: string
}

/** Payload of a streamed `data-action-item` part (a board mutation). */
export type ActionItemEvent = {
  op: "created" | "updated" | "deleted"
  id: string
  session_id: string
  task: string
  owner: string | null
  due_date: string | null
  status: ActionStatus
  created_at: string
  updated_at: string
}
