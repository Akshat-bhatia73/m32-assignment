import { CalendarDays, ListTodo } from "lucide-react"
import { useState } from "react"

import { ActionBoard } from "@/components/board/action-board"
import { CalendarPanel } from "@/components/board/calendar-panel"
import { useBoardStore } from "@/stores/board-store"
import { cn } from "@/lib/utils"

type Tab = "board" | "calendar"

/** Right column: Action Board and the user's calendar agenda, switchable via tabs. */
export function RightSidebar({ onChanged }: { onChanged: () => void }) {
  const [tab, setTab] = useState<Tab>("board")
  const itemCount = useBoardStore((s) => s.items.length)

  const tabs: { key: Tab; label: string; icon: typeof ListTodo }[] = [
    { key: "board", label: "Action Board", icon: ListTodo },
    { key: "calendar", label: "Calendar", icon: CalendarDays },
  ]

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-[3.75rem] shrink-0 items-center gap-1 border-b border-border px-2">
        {tabs.map(({ key, label, icon: Icon }) => {
          const active = tab === key
          return (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
              )}
            >
              <Icon className="size-4" />
              {label}
              {key === "board" && itemCount > 0 ? (
                <span className="rounded-full bg-muted px-1.5 text-xs text-muted-foreground">
                  {itemCount}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>

      {tab === "board" ? <ActionBoard onChanged={onChanged} /> : <CalendarPanel />}
    </div>
  )
}
