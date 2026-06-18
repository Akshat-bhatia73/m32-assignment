import type { LucideIcon } from "lucide-react"
import { XIcon } from "lucide-react"
import type { ComponentProps, HTMLAttributes } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

// AI Elements "Artifact" — a structured container for generated/attached content. Adapted to our
// Base UI scaffold (the upstream ArtifactAction uses Radix `Tooltip asChild`; here we use a native
// title attribute instead so it stays compatible).

export type ArtifactProps = HTMLAttributes<HTMLDivElement>

export const Artifact = ({ className, ...props }: ArtifactProps) => (
  <div
    className={cn(
      "flex flex-col overflow-hidden rounded-xl border border-border bg-background shadow-sm",
      className
    )}
    {...props}
  />
)

export type ArtifactHeaderProps = HTMLAttributes<HTMLDivElement>

export const ArtifactHeader = ({ className, ...props }: ArtifactHeaderProps) => (
  <div
    className={cn(
      "flex items-center justify-between gap-3 border-b border-border bg-muted/50 px-4 py-3",
      className
    )}
    {...props}
  />
)

export type ArtifactCloseProps = ComponentProps<typeof Button>

export const ArtifactClose = ({
  className,
  children,
  size = "icon-sm",
  variant = "ghost",
  ...props
}: ArtifactCloseProps) => (
  <Button
    className={cn("text-muted-foreground hover:text-foreground", className)}
    size={size}
    type="button"
    variant={variant}
    {...props}
  >
    {children ?? <XIcon className="size-4" />}
    <span className="sr-only">Close</span>
  </Button>
)

export type ArtifactTitleProps = HTMLAttributes<HTMLParagraphElement>

export const ArtifactTitle = ({ className, ...props }: ArtifactTitleProps) => (
  <p className={cn("truncate text-sm font-medium text-foreground", className)} {...props} />
)

export type ArtifactDescriptionProps = HTMLAttributes<HTMLParagraphElement>

export const ArtifactDescription = ({ className, ...props }: ArtifactDescriptionProps) => (
  <p className={cn("text-xs text-muted-foreground", className)} {...props} />
)

export type ArtifactActionsProps = HTMLAttributes<HTMLDivElement>

export const ArtifactActions = ({ className, ...props }: ArtifactActionsProps) => (
  <div className={cn("flex items-center gap-1", className)} {...props} />
)

export type ArtifactActionProps = ComponentProps<typeof Button> & {
  tooltip?: string
  label?: string
  icon?: LucideIcon
}

export const ArtifactAction = ({
  tooltip,
  label,
  icon: Icon,
  children,
  className,
  size = "icon-sm",
  variant = "ghost",
  ...props
}: ArtifactActionProps) => (
  <Button
    className={cn("text-muted-foreground hover:text-foreground", className)}
    size={size}
    title={tooltip}
    type="button"
    variant={variant}
    {...props}
  >
    {Icon ? <Icon className="size-4" /> : children}
    <span className="sr-only">{label || tooltip}</span>
  </Button>
)

export type ArtifactContentProps = HTMLAttributes<HTMLDivElement>

export const ArtifactContent = ({ className, ...props }: ArtifactContentProps) => (
  <div className={cn("min-h-0 flex-1 overflow-auto p-4", className)} {...props} />
)
