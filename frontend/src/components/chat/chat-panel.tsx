import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type DynamicToolUIPart, type ToolUIPart, type UIMessage } from "ai"
import { Paperclip, Send, Sparkles } from "lucide-react"
import { type ClipboardEvent, type KeyboardEvent, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import { ArtifactChip } from "@/components/chat/artifact-chip"
import { ArtifactViewer } from "@/components/chat/artifact-viewer"
import { ThinkingTrail } from "@/components/chat/thinking-trail"
import { ToolPartView } from "@/components/chat/tool-part"
import { IconButton } from "@/components/ui/icon-button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { api, API_BASE } from "@/lib/api"
import type { Artifact, ActionItemEvent, SessionTitleEvent, StatusEvent } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useBoardStore } from "@/stores/board-store"

const UPLOAD_ACCEPT = ".txt,.md,.markdown,.csv,.log,.pdf,image/png,image/jpeg,image/webp,image/gif"
// A pasted blob longer than this is captured as an artifact instead of filling the composer.
const PASTE_ARTIFACT_CHARS = 1200

// Tighten Streamdown's default vertical rhythm so replies read as compact prose.
const MARKDOWN_CLASS = cn(
  "leading-relaxed",
  "[&_p]:my-0 [&_p+p]:mt-3",
  "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:ps-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:ps-5",
  "[&_li]:my-1 [&_li]:marker:text-muted-foreground",
  "[&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:mt-3 [&_h3]:mb-1.5",
  "[&_pre]:my-3 [&_code]:text-[0.85em]"
)

function isToolPart(part: UIMessage["parts"][number]): part is ToolUIPart | DynamicToolUIPart {
  return part.type === "dynamic-tool" || part.type.startsWith("tool-")
}

function messageArtifacts(message: UIMessage): Artifact[] {
  return (message.metadata as { artifacts?: Artifact[] } | undefined)?.artifacts ?? []
}

export function ChatPanel({
  sessionId,
  title,
  initialMessages,
  onTurnComplete,
  onSessionTitle,
}: {
  sessionId: string
  title: string
  initialMessages: UIMessage[]
  onTurnComplete: () => void
  onSessionTitle: (id: string, title: string) => void
}) {
  const applyEvent = useBoardStore((s) => s.applyEvent)
  const clearRecent = useBoardStore((s) => s.clearRecent)
  const [input, setInput] = useState("")
  const [pending, setPending] = useState<Artifact[]>([])
  const [viewing, setViewing] = useState<Artifact | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { messages, sendMessage, status } = useChat({
    id: sessionId,
    messages: initialMessages,
    transport: new DefaultChatTransport({
      api: `${API_BASE}/chat/stream`,
      credentials: "include",
      prepareSendMessagesRequest: ({ id, messages }) => {
        const last = messages[messages.length - 1]
        const text =
          last?.parts
            ?.filter((p) => p.type === "text")
            .map((p) => (p as { text: string }).text)
            .join("") ?? ""
        const artifacts = (last ? messageArtifacts(last) : []).map((a) => ({
          id: a.id,
          name: a.name,
          kind: a.kind,
          content: a.content,
          mime: a.mime ?? null,
        }))
        return { body: { session_id: id, message: text, artifacts } }
      },
    }),
    onData: (dataPart) => {
      if (dataPart.type === "data-action-item") {
        applyEvent(dataPart.data as ActionItemEvent)
      } else if (dataPart.type === "data-session-title") {
        const { session_id, title } = dataPart.data as SessionTitleEvent
        onSessionTitle(session_id, title)
      }
    },
    onFinish: () => onTurnComplete(),
  })

  // Backup reconcile: apply any board parts present on the latest assistant message.
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (!last || last.role !== "assistant") return
    for (const part of last.parts) {
      if (part.type === "data-action-item") {
        applyEvent((part as { data: ActionItemEvent }).data)
      }
    }
  }, [messages, applyEvent])

  const busy = status === "submitted" || status === "streaming"

  function addArtifact(a: Artifact) {
    setPending((prev) => [...prev, a])
  }

  function removeArtifact(id: string) {
    setPending((prev) => {
      const target = prev.find((a) => a.id === id)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      return prev.filter((a) => a.id !== id)
    })
  }

  function submit() {
    const text = input.trim()
    if ((!text && pending.length === 0) || busy) return
    clearRecent()
    sendMessage({ text, metadata: { artifacts: pending } })
    setInput("")
    setPending([])
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const text = e.clipboardData.getData("text")
    if (text.length >= PASTE_ARTIFACT_CHARS) {
      e.preventDefault()
      addArtifact({
        id: crypto.randomUUID(),
        name: "Pasted text",
        kind: "paste",
        content: text,
      })
      toast.success("Captured pasted text as an attachment", {
        description: "Open it any time, or send to extract action items.",
      })
    }
  }

  async function onFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = "" // allow re-selecting the same file
    if (!file) return
    setUploading(true)
    try {
      const res = await api.extractTranscript(file)
      const isImage = res.source === "image"
      addArtifact({
        id: crypto.randomUUID(),
        name: res.filename,
        kind: isImage ? "image" : "file",
        content: res.text,
        mime: file.type || null,
        previewUrl: isImage ? URL.createObjectURL(file) : undefined,
      })
      toast.success(isImage ? "Transcribed screenshot" : `Attached ${res.filename}`, {
        description: "Open it to review, or send to extract action items.",
      })
    } catch (err) {
      toast.error("Couldn't read that file", {
        description: err instanceof Error ? err.message : "Please try a different file.",
      })
    } finally {
      setUploading(false)
    }
  }

  const waiting = status === "submitted"
  const canSend = (input.trim().length > 0 || pending.length > 0) && !busy

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Column header — aligns with the sidebar and Action Board headers. */}
      <div className="flex h-[3.75rem] shrink-0 flex-col justify-center border-b border-border px-5">
        <h2 className="truncate text-sm font-semibold text-foreground">{title || "Untitled"}</h2>
        <p className="text-xs text-muted-foreground">Meeting workspace</p>
      </div>

      <Conversation className="min-h-0 flex-1">
        <ConversationContent className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-5 py-6">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((message, mi) => {
              const isAssistant = message.role === "assistant"
              const isLastStreaming = mi === messages.length - 1 && busy
              const statuses = message.parts
                .filter((p) => p.type === "data-status")
                .map((p) => (p as { data: StatusEvent }).data)
              const artifacts = messageArtifacts(message)
              return (
                <Message
                  key={message.id}
                  from={message.role}
                  className={cn(isAssistant && "flex-row items-start gap-3")}
                >
                  {isAssistant ? (
                    <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Sparkles className="size-3.5" />
                    </div>
                  ) : null}
                  <MessageContent className={cn(isAssistant && "min-w-0 flex-1")}>
                    {isAssistant && statuses.length > 0 ? (
                      <ThinkingTrail steps={statuses} active={isLastStreaming} />
                    ) : null}
                    {artifacts.length > 0 ? (
                      <div className="flex flex-wrap gap-2 group-[.is-user]:justify-end">
                        {artifacts.map((a) => (
                          <ArtifactChip key={a.id} artifact={a} onOpen={setViewing} />
                        ))}
                      </div>
                    ) : null}
                    {message.parts.map((part, i) => {
                      if (part.type === "text") {
                        if (!part.text) return null
                        return (
                          <MessageResponse key={i} className={MARKDOWN_CLASS}>
                            {part.text}
                          </MessageResponse>
                        )
                      }
                      if (isToolPart(part)) {
                        return <ToolPartView key={i} part={part} />
                      }
                      return null
                    })}
                  </MessageContent>
                </Message>
              )
            })
          )}
          {waiting ? (
            <div className="flex items-center gap-3">
              <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Sparkles className="size-3.5" />
              </div>
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner className="size-3.5" />
                Thinking…
              </span>
            </div>
          ) : null}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="shrink-0 px-5 pb-5 pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
          className="mx-auto w-full max-w-3xl rounded-2xl border border-border bg-card p-2 shadow-sm transition-shadow focus-within:border-ring/60 focus-within:shadow-md"
        >
          {pending.length > 0 ? (
            <div className="flex flex-wrap gap-2 p-1 pb-2">
              {pending.map((a) => (
                <ArtifactChip
                  key={a.id}
                  artifact={a}
                  onOpen={setViewing}
                  onRemove={removeArtifact}
                />
              ))}
            </div>
          ) : null}
          <div className="flex items-end gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={UPLOAD_ACCEPT}
              className="hidden"
              onChange={onFileSelected}
            />
            <IconButton
              tooltip="Attach a transcript or screenshot"
              variant="ghost"
              className="size-9 shrink-0 text-muted-foreground"
              disabled={uploading || busy}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? <Spinner className="size-4" /> : <Paperclip className="size-4" />}
            </IconButton>
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              onPaste={onPaste}
              rows={1}
              placeholder={
                uploading
                  ? "Reading your file…"
                  : "Paste meeting notes, attach a transcript, or ask me to draft a follow-up…"
              }
              className="max-h-40 min-h-9 flex-1 resize-none self-center border-0 bg-transparent px-1 py-1.5 shadow-none focus-visible:ring-0 dark:bg-transparent"
            />
            <IconButton
              tooltip="Send"
              type="submit"
              className="size-9 shrink-0"
              disabled={!canSend}
            >
              {busy ? <Spinner className="size-4" /> : <Send className="size-4" />}
            </IconButton>
          </div>
        </form>
        <p className="mx-auto mt-2 max-w-3xl px-1 text-center text-xs text-muted-foreground">
          Enter to send · Shift+Enter for a new line
        </p>
      </div>

      <ArtifactViewer artifact={viewing} onClose={() => setViewing(null)} />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
        <Sparkles className="size-6" />
      </div>
      <div className="space-y-1.5">
        <p className="text-base font-semibold text-foreground">Turn a meeting into done</p>
        <p className="mx-auto max-w-sm text-sm leading-relaxed text-muted-foreground">
          Paste your notes — or attach a transcript or screenshot — and I'll pull out action items,
          draft the follow-up email, and add calendar events, all from this chat.
        </p>
      </div>
    </div>
  )
}
