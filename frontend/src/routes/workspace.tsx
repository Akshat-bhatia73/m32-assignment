import { useQuery, useQueryClient } from "@tanstack/react-query"
import type { UIMessage } from "ai"
import { useCallback, useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { RightSidebar } from "@/components/board/right-sidebar"
import { ChatPanel } from "@/components/chat/chat-panel"
import { SessionSidebar } from "@/components/layout/session-sidebar"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useCurrentUser } from "@/hooks/use-auth"
import { api } from "@/lib/api"
import type { ChatMessage, Session } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useBoardStore } from "@/stores/board-store"

function toUIMessages(messages: ChatMessage[]): UIMessage[] {
  return messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      parts: [
        { type: "text", text: m.content },
        // Replay structured cards (email draft / calendar proposal) so a reloaded turn renders
        // them as cards, not just the plain-text twin.
        ...(m.data_parts ?? []).map((p) => ({ type: `data-${p.type}`, data: p.data })),
      ] as UIMessage["parts"],
      // Rehydrate attachment chips + sent time for past turns.
      metadata: { createdAt: m.created_at, artifacts: m.artifacts ?? undefined },
    }))
}

type MobilePane = "sessions" | "chat" | "board"

export function WorkspacePage() {
  const queryClient = useQueryClient()
  const setAll = useBoardStore((s) => s.setAll)
  const reset = useBoardStore((s) => s.reset)
  const [searchParams, setSearchParams] = useSearchParams()
  const [mobilePane, setMobilePane] = useState<MobilePane>("chat")
  // Honor a ?session=<id> deep link (e.g. "Open" from the overview screen) on first load.
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("session"))
  const creatingRef = useRef(false)

  const sessionsQuery = useQuery({ queryKey: ["sessions"], queryFn: api.listSessions })
  const sessions = sessionsQuery.data
  const { data: currentUser } = useCurrentUser()

  // The deep-link param is consumed into state above; drop it so the URL stays clean.
  useEffect(() => {
    if (searchParams.get("session")) setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  // Ensure there's always at least one session to work in (create one when the user has none).
  useEffect(() => {
    if (!sessions || sessions.length > 0 || creatingRef.current) return
    creatingRef.current = true
    api.createSession().then((s) => {
      queryClient.setQueryData<Session[]>(["sessions"], [s])
      setSelectedId(s.id)
      creatingRef.current = false
    })
  }, [sessions, queryClient])

  // Effective selection: the chosen session if still present, otherwise the most recent.
  const currentId =
    selectedId && sessions?.some((s) => s.id === selectedId) ? selectedId : sessions?.[0]?.id

  const messagesQuery = useQuery({
    queryKey: ["messages", currentId],
    queryFn: () => api.getMessages(currentId!),
    enabled: !!currentId,
  })

  const actionsQuery = useQuery({
    queryKey: ["actions", currentId],
    queryFn: () => api.getActions(currentId!),
    enabled: !!currentId,
  })

  // Clear the board immediately on session switch so we never flash the previous board.
  useEffect(() => {
    reset()
  }, [currentId, reset])

  // Seed the board store whenever the authoritative list loads/refreshes.
  useEffect(() => {
    if (actionsQuery.data) setAll(actionsQuery.data)
  }, [actionsQuery.data, setAll])

  useEffect(() => () => reset(), [reset])

  const refresh = useCallback(async () => {
    if (!currentId) return
    const items = await api.getActions(currentId)
    setAll(items)
    // Keep React Query's cache authoritative too, so switching sessions and back doesn't
    // re-seed the board from a stale snapshot that's missing this turn's items.
    queryClient.setQueryData(["actions", currentId], items)
    // A turn may have created or moved calendar events — refresh the agenda.
    queryClient.invalidateQueries({ queryKey: ["calendar-events"] })
  }, [currentId, setAll, queryClient])

  const handleNew = useCallback(async () => {
    const s = await api.createSession()
    queryClient.setQueryData<Session[]>(["sessions"], (prev) => [s, ...(prev ?? [])])
    setSelectedId(s.id)
    setMobilePane("chat")
  }, [queryClient])

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id)
    setMobilePane("chat")
  }, [])

  const handleDelete = useCallback(
    async (id: string) => {
      await api.deleteSession(id)
      const remaining = (sessions ?? []).filter((s) => s.id !== id)
      queryClient.setQueryData<Session[]>(["sessions"], remaining)
      if (selectedId === id) setSelectedId(remaining[0]?.id ?? null)
    },
    [sessions, selectedId, queryClient]
  )

  // Live auto-title from the chat stream → update the sidebar in place.
  const handleSessionTitle = useCallback(
    (id: string, title: string) => {
      queryClient.setQueryData<Session[]>(["sessions"], (prev) =>
        (prev ?? []).map((s) => (s.id === id ? { ...s, title } : s))
      )
    },
    [queryClient]
  )

  const ready = currentId && messagesQuery.data && actionsQuery.data

  // A shared session is read-only for everyone except the member who started it.
  const currentSession = sessions?.find((s) => s.id === currentId)
  const isOwner = !currentSession || !currentUser || currentSession.owner_id === currentUser.id
  const ownerName = currentSession?.owner_name ?? "the owner"

  return (
    <div className="flex h-svh flex-col bg-background">
      {/* mobile pane switch */}
      <div className="flex shrink-0 items-center gap-1 border-b border-border bg-card p-2 md:hidden">
        {(["sessions", "chat", "board"] as MobilePane[]).map((pane) => (
          <Button
            key={pane}
            variant={mobilePane === pane ? "secondary" : "ghost"}
            size="sm"
            className="flex-1 capitalize"
            onClick={() => setMobilePane(pane)}
          >
            {pane === "board" ? "Action Board" : pane}
          </Button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Sidebar: persistent on desktop, a pane on mobile. */}
        <div
          className={cn(
            "w-full shrink-0 border-r border-border md:w-[240px] lg:w-[260px]",
            mobilePane === "sessions" ? "block" : "hidden md:block"
          )}
        >
          <SessionSidebar
            sessions={sessions ?? []}
            currentId={currentId}
            onSelect={handleSelect}
            onNew={handleNew}
            onDelete={handleDelete}
          />
        </div>

        {!ready ? (
          <div className="flex flex-1 items-center justify-center">
            <Spinner className="size-6 text-muted-foreground" />
          </div>
        ) : (
          <>
            <div
              className={cn(
                "min-w-0 flex-1",
                mobilePane === "chat" ? "block" : "hidden md:block"
              )}
            >
              <ChatPanel
                key={currentId}
                sessionId={currentId!}
                title={currentSession?.title ?? "Untitled"}
                initialMessages={toUIMessages(messagesQuery.data)}
                onTurnComplete={refresh}
                onSessionTitle={handleSessionTitle}
                readOnly={!isOwner}
                ownerName={ownerName}
              />
            </div>
            <div
              className={cn(
                "w-full shrink-0 border-l border-border bg-card md:w-[340px] lg:w-[380px]",
                mobilePane === "board" ? "block" : "hidden md:block"
              )}
            >
              <RightSidebar onChanged={refresh} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
