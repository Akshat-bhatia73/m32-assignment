import { CalendarPlus, Check, TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { CalendarProposalEvent } from "@/lib/types"

function formatSlot(start: string, date: string): string {
  const d = new Date(start)
  if (Number.isNaN(d.getTime())) return date
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

/** Renders proposed calendar events as a structured card, badging schedule conflicts. */
export function CalendarProposalCard({
  proposal,
  onConfirm,
  confirmed,
  busy,
}: {
  proposal: CalendarProposalEvent
  onConfirm: () => void
  confirmed: boolean
  busy: boolean
}) {
  const conflicts = proposal.events.filter((e) => e.conflict).length

  return (
    <div className="w-full overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <CalendarPlus className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">
          {proposal.events.length} calendar event{proposal.events.length !== 1 ? "s" : ""}
        </span>
        {conflicts > 0 ? (
          <span className="ms-auto flex items-center gap-1 text-xs font-medium text-destructive">
            <TriangleAlert className="size-3.5" />
            {conflicts} overlap{conflicts !== 1 ? "s" : ""}
          </span>
        ) : null}
      </div>
      <ul className="divide-y divide-border">
        {proposal.events.map((e, i) => (
          <li key={i} className="flex flex-col gap-1 px-4 py-3">
            <span className="text-sm font-medium text-foreground">{e.summary}</span>
            <span className="text-xs text-muted-foreground">{formatSlot(e.start, e.date)}</span>
            {e.conflict ? (
              <span className="mt-0.5 flex items-center gap-1 text-xs text-destructive">
                <TriangleAlert className="size-3.5 shrink-0" />
                Overlaps “{e.conflict}”
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      <div className="flex items-center justify-end px-4 py-3">
        <Button size="sm" onClick={onConfirm} disabled={confirmed || busy}>
          {confirmed ? <Check className="size-4" /> : <CalendarPlus className="size-4" />}
          {confirmed ? "Added" : "Add to calendar"}
        </Button>
      </div>
    </div>
  )
}
