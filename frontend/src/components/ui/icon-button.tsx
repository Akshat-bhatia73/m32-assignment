import type { ComponentProps } from "react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

type TooltipSide = "top" | "bottom" | "left" | "right"

/** An icon-only Button that always carries a tooltip + accessible label. Round by default. */
export function IconButton({
  tooltip,
  tooltipSide = "top",
  size = "icon",
  className,
  children,
  ...props
}: ComponentProps<typeof Button> & {
  tooltip: string
  tooltipSide?: TooltipSide
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            size={size}
            aria-label={tooltip}
            className={cn("rounded-full", className)}
            {...props}
          >
            {children}
          </Button>
        }
      />
      <TooltipContent side={tooltipSide}>{tooltip}</TooltipContent>
    </Tooltip>
  )
}
