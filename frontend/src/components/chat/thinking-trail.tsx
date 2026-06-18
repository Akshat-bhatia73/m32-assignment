import { Check } from "lucide-react"

import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import type { StatusEvent } from "@/lib/types"

/** A calm vertical trail of the agent's "thinking" steps for one assistant turn. */
export function ThinkingTrail({ steps, active }: { steps: StatusEvent[]; active: boolean }) {
  if (steps.length === 0) return null
  const lastIndex = steps.length - 1

  return (
    <div className="mb-1 flex flex-col gap-1.5">
      {steps.map((step, i) => {
        const isCurrent = active && i === lastIndex
        return (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="flex size-4 shrink-0 items-center justify-center">
              {isCurrent ? (
                <Spinner className="size-3.5 text-muted-foreground" />
              ) : (
                <Check className="size-3.5 text-primary" />
              )}
            </span>
            <span className={cn(isCurrent ? "text-foreground" : "text-muted-foreground")}>
              {step.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
