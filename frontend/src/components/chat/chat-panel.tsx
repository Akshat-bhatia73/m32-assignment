import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type DynamicToolUIPart, type ToolUIPart, type UIMessage } from "ai"
import { Send, Sparkles } from "lucide-react"
import { type KeyboardEvent, useEffect, useState } from "react"

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import { ToolPartView } from "@/components/chat/tool-part"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { API_BASE } from "@/lib/api"
import type { ActionItemEvent } from "@/lib/types"
import { useBoardStore } from "@/stores/board-store"

function isToolPart(part: UIMessage["parts"][number]): part is ToolUIPart | DynamicToolUIPart {
  return part.type === "dynamic-tool" || part.type.startsWith("tool-")
}

export function ChatPanel({
  sessionId,
  initialMessages,
  onTurnComplete,
}: {
  sessionId: string
  initialMessages: UIMessage[]
  onTurnComplete: () => void
}) {
  const applyEvent = useBoardStore((s) => s.applyEvent)
  const clearRecent = useBoardStore((s) => s.clearRecent)
  const [input, setInput] = useState("")

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
        return { body: { session_id: id, message: text } }
      },
    }),
    onData: (dataPart) => {
      if (dataPart.type === "data-action-item") {
        applyEvent(dataPart.data as ActionItemEvent)
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

  function submit() {
    const text = input.trim()
    if (!text || busy) return
    clearRecent()
    sendMessage({ text })
    setInput("")
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const waiting = status === "submitted"

  return (
    <div className="flex h-full flex-col">
      <Conversation className="min-h-0 flex-1">
        <ConversationContent className="mx-auto w-full max-w-2xl">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((message) => (
              <Message key={message.id} from={message.role}>
                <MessageContent>
                  {message.parts.map((part, i) => {
                    if (part.type === "text") {
                      return <MessageResponse key={i}>{part.text}</MessageResponse>
                    }
                    if (isToolPart(part)) {
                      return <ToolPartView key={i} part={part} />
                    }
                    return null
                  })}
                </MessageContent>
              </Message>
            ))
          )}
          {waiting ? (
            <div className="flex items-center gap-2 px-1 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              Thinking…
            </div>
          ) : null}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="border-t border-border bg-card p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
          className="mx-auto flex w-full max-w-2xl items-end gap-2 rounded-xl border border-border bg-background p-2 focus-within:ring-1 focus-within:ring-ring"
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Paste meeting notes, or ask me to draft a follow-up…"
            className="max-h-40 min-h-9 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
          />
          <Button
            type="submit"
            size="icon"
            aria-label="Send"
            disabled={!input.trim() || busy}
          >
            {busy ? <Spinner className="size-4" /> : <Send className="size-4" />}
          </Button>
        </form>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <div className="flex size-11 items-center justify-center rounded-xl bg-muted text-muted-foreground">
        <Sparkles className="size-5" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">Turn a meeting into done</p>
        <p className="mt-1 max-w-xs text-sm text-muted-foreground">
          Paste your notes and I'll pull out action items, draft the follow-up email, and add
          calendar events — all from this chat.
        </p>
      </div>
    </div>
  )
}
