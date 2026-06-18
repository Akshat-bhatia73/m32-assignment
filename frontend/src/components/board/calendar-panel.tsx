import { useQuery } from "@tanstack/react-query"
import { CalendarClock, CalendarX, TriangleAlert } from "lucide-react"

import { Spinner } from "@/components/ui/spinner"
import { api } from "@/lib/api"
import type { CalendarEvent } from "@/lib/types"

type DayGroup = { key: string; label: string; events: CalendarEvent[] }

function startMs(e: CalendarEvent): number {
  const t = e.start ? new Date(e.start).getTime() : NaN
  return Number.isNaN(t) ? 0 : t
}

function endMs(e: CalendarEvent): number {
  const t = e.end ? new Date(e.end).getTime() : NaN
  return Number.isNaN(t) ? startMs(e) : t
}

/** Flag events that overlap another timed event in the list (excludes all-day). */
function overlapIds(events: CalendarEvent[]): Set<string> {
  const timed = events.filter((e) => !e.all_day)
  const ids = new Set<string>()
  for (let i = 0; i < timed.length; i++) {
    for (let j = i + 1; j < timed.length; j++) {
      if (startMs(timed[i]) < endMs(timed[j]) && startMs(timed[j]) < endMs(timed[i])) {
        ids.add(timed[i].id)
        ids.add(timed[j].id)
      }
    }
  }
  return ids
}

function dayLabel(d: Date): string {
  const today = new Date()
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const days = Math.round((startOfDay(d) - startOfDay(today)) / 86_400_000)
  if (days === 0) return "Today"
  if (days === 1) return "Tomorrow"
  return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })
}

function groupByDay(events: CalendarEvent[]): DayGroup[] {
  const groups = new Map<string, DayGroup>()
  for (const e of [...events].sort((a, b) => startMs(a) - startMs(b))) {
    if (!e.start) continue
    const d = new Date(e.start)
    if (Number.isNaN(d.getTime())) continue
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    if (!groups.has(key)) groups.set(key, { key, label: dayLabel(d), events: [] })
    groups.get(key)!.events.push(e)
  }
  return [...groups.values()]
}

function timeLabel(e: CalendarEvent): string {
  if (e.all_day) return "All day"
  if (!e.start) return ""
  const d = new Date(e.start)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

export function CalendarPanel() {
  const query = useQuery({ queryKey: ["calendar-events"], queryFn: () => api.getCalendarEvents(7) })

  const connected = query.data?.connected ?? false
  const events = query.data?.events ?? []
  const groups = groupByDay(events)
  const conflicts = overlapIds(events)

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      {query.isLoading ? (
        <div className="flex h-full items-center justify-center">
          <Spinner className="size-5 text-muted-foreground" />
        </div>
      ) : !connected ? (
        <Empty
          icon={CalendarX}
          title="Calendar not connected"
          body="Connect Google Calendar in Settings to see your upcoming schedule here."
        />
      ) : groups.length === 0 ? (
        <Empty
          icon={CalendarClock}
          title="Nothing coming up"
          body="No events in the next 7 days."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <div key={g.key} className="flex flex-col gap-1.5">
              <p className="px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {g.label}
              </p>
              {g.events.map((e) => {
                const clash = conflicts.has(e.id)
                return (
                  <div
                    key={e.id}
                    className="flex items-start gap-3 rounded-lg border border-border bg-card p-2.5"
                  >
                    <span className="w-16 shrink-0 pt-px text-xs font-medium text-muted-foreground">
                      {timeLabel(e)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-foreground">{e.summary}</p>
                      {clash ? (
                        <span className="mt-0.5 flex items-center gap-1 text-xs text-destructive">
                          <TriangleAlert className="size-3" />
                          Overlaps another event
                        </span>
                      ) : null}
                    </div>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Empty({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof CalendarX
  title: string
  body: string
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{body}</p>
    </div>
  )
}
