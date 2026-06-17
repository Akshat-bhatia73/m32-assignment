import { useQuery } from "@tanstack/react-query"
import type { UIMessage } from "ai"
import { useCallback, useEffect, useState } from "react"

import { ActionBoard } from "@/components/board/action-board"
import { ChatPanel } from "@/components/chat/chat-panel"
import { AppHeader } from "@/components/layout/app-header"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { api } from "@/lib/api"
import type { ChatMessage } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useBoardStore } from "@/stores/board-store"

function toUIMessages(messages: ChatMessage[]): UIMessage[] {
  return messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      parts: [{ type: "text", text: m.content }],
    }))
}

export function WorkspacePage() {
  const setAll = useBoardStore((s) => s.setAll)
  const reset = useBoardStore((s) => s.reset)
  const [mobilePane, setMobilePane] = useState<"chat" | "board">("chat")

  // Ensure exactly one working session (most recent, or create one).
  const sessionQuery = useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      const sessions = await api.listSessions()
      return sessions[0] ?? (await api.createSession("Workspace"))
    },
  })
  const sessionId = sessionQuery.data?.id

  const messagesQuery = useQuery({
    queryKey: ["messages", sessionId],
    queryFn: () => api.getMessages(sessionId!),
    enabled: !!sessionId,
  })

  const actionsQuery = useQuery({
    queryKey: ["actions", sessionId],
    queryFn: () => api.getActions(sessionId!),
    enabled: !!sessionId,
  })

  // Seed the board store whenever the authoritative list loads/refreshes.
  useEffect(() => {
    if (actionsQuery.data) setAll(actionsQuery.data)
  }, [actionsQuery.data, setAll])

  useEffect(() => () => reset(), [reset])

  const refresh = useCallback(async () => {
    if (!sessionId) return
    setAll(await api.getActions(sessionId))
  }, [sessionId, setAll])

  const ready = sessionId && messagesQuery.data && actionsQuery.data

  return (
    <div className="flex h-svh flex-col bg-background">
      <AppHeader />

      {/* mobile pane switch */}
      <div className="flex shrink-0 items-center gap-1 border-b border-border bg-card p-2 md:hidden">
        <Button
          variant={mobilePane === "chat" ? "secondary" : "ghost"}
          size="sm"
          className="flex-1"
          onClick={() => setMobilePane("chat")}
        >
          Chat
        </Button>
        <Button
          variant={mobilePane === "board" ? "secondary" : "ghost"}
          size="sm"
          className="flex-1"
          onClick={() => setMobilePane("board")}
        >
          Action Board
        </Button>
      </div>

      {!ready ? (
        <div className="flex flex-1 items-center justify-center">
          <Spinner className="size-6 text-muted-foreground" />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div
            className={cn(
              "min-w-0 flex-1",
              mobilePane === "board" && "hidden md:block"
            )}
          >
            <ChatPanel
              sessionId={sessionId}
              initialMessages={toUIMessages(messagesQuery.data)}
              onTurnComplete={refresh}
            />
          </div>
          <div
            className={cn(
              "w-full shrink-0 border-l border-border bg-card md:w-[360px] lg:w-[400px]",
              mobilePane === "chat" && "hidden md:block"
            )}
          >
            <ActionBoard onChanged={refresh} />
          </div>
        </div>
      )}
    </div>
  )
}
