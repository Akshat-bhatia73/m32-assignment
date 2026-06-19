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

export type ArtifactKind = "file" | "image" | "paste"

/** An attachment carried with a turn — an uploaded file or a long pasted text blob. */
export type Artifact = {
  id: string
  name: string
  kind: ArtifactKind
  content: string
  mime?: string | null
  /** Client-only object URL for live image preview (not persisted). */
  previewUrl?: string
}

/** A structured stream part persisted with a message, replayed as a card on reload. */
export type PersistedDataPart = {
  type: string // e.g. "email-draft" | "calendar-proposal"
  data: unknown
}

export type ChatMessage = {
  id: string
  role: "user" | "assistant" | "tool"
  content: string
  artifacts?: Artifact[] | null
  data_parts?: PersistedDataPart[] | null
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

/** An action item plus the title of its session (overview screen). */
export type ActionItemWithSession = ActionItem & {
  session_title: string
}

/** Plain text extracted from an uploaded transcript file or screenshot. */
export type ExtractedTranscript = {
  text: string
  filename: string
  source: "upload" | "image"
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

/** Payload of a streamed `data-session-title` part (auto-generated title). */
export type SessionTitleEvent = {
  session_id: string
  title: string
}

/** Payload of a streamed `data-status` part (a "thinking" step). */
export type StatusEvent = {
  label: string
  node: string | null
}

/** Payload of a streamed `data-email-draft` part (a follow-up email awaiting send). */
export type EmailDraftEvent = {
  to: string[]
  subject: string
  body: string
}

/** Composio connection status for the current user. */
export type IntegrationStatus = {
  gmail: boolean
  googlecalendar: boolean
}

/** A normalized Google Calendar event for the sidebar agenda. */
export type CalendarEvent = {
  id: string
  summary: string
  start: string | null
  end: string | null
  all_day: boolean
}

export type CalendarEventsResponse = {
  connected: boolean
  events: CalendarEvent[]
}

export type OrgRole = "owner" | "member"

export type OrgMember = {
  id: string
  name: string | null
  email: string
  role: OrgRole
}

export type Invitation = {
  id: string
  email: string
  name: string | null
  role: OrgRole
  status: "pending" | "accepted" | "revoked"
  created_at: string
}

/** The current user's organization (workspace), members, and pending invites. */
export type Org = {
  id: string
  name: string
  role: OrgRole // the current user's role
  member_cap: number
  members: OrgMember[]
  invites: Invitation[]
}

/** One proposed calendar event in a `data-calendar-proposal` part. */
export type CalendarProposalItem = {
  summary: string
  date: string
  /** ISO start the event would occupy (date + default 9:00 block). */
  start: string
  /** Title of an existing event this would collide with, if any. */
  conflict: string | null
}

/** Payload of a streamed `data-calendar-proposal` part (events awaiting confirmation). */
export type CalendarProposalEvent = {
  events: CalendarProposalItem[]
}

/** Payload of a streamed `data-calendar-action` part — a reschedule/cancel awaiting approval. */
export type CalendarActionEvent = {
  action: "reschedule_event" | "delete_event"
  title: string
  /** Human-readable target time for a reschedule, or null for a cancellation. */
  when: string | null
  /** One-line description of what will happen. */
  detail: string
}

/** Reasoning effort for reasoning-capable models. */
export type ReasoningEffort = "low" | "medium" | "high"

/** A selectable LLM from the backend catalog (only models with a configured key are returned). */
export type ModelInfo = {
  id: string
  label: string
  provider: "openai" | "google"
  blurb: string
  supports_reasoning: boolean
  reasoning_options: ReasoningEffort[]
  default_reasoning: ReasoningEffort | null
}

/** Response of GET /models — the available catalog plus the server's default pick. */
export type ModelsResponse = {
  default: { model: string; reasoning: ReasoningEffort | null }
  models: ModelInfo[]
}
