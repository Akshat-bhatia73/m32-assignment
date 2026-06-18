import { ClipboardList } from "lucide-react"

import { ActionCard } from "@/components/board/action-card"
import { useBoardStore } from "@/stores/board-store"

export function ActionBoard({ onChanged }: { onChanged: () => void }) {
  const items = useBoardStore((s) => s.items)
  const recentlyChanged = useBoardStore((s) => s.recentlyChanged)

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {items.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <ClipboardList className="size-5" />
            </div>
            <p className="text-sm font-medium text-foreground">No action items yet</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Paste meeting notes in the chat and I'll pull out the tasks.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {items.map((item) => (
              <ActionCard
                key={item.id}
                item={item}
                highlighted={recentlyChanged.has(item.id)}
                onChanged={onChanged}
              />
            ))}
          </div>
        )}
    </div>
  )
}
