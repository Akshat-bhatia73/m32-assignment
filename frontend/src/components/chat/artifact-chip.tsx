import { FileText, ImageIcon, StickyNote, X } from "lucide-react"

import { IconButton } from "@/components/ui/icon-button"
import { artifactMeta } from "@/lib/artifacts"
import { cn } from "@/lib/utils"
import type { Artifact, ArtifactKind } from "@/lib/types"

const KIND_ICON: Record<ArtifactKind, typeof FileText> = {
  file: FileText,
  image: ImageIcon,
  paste: StickyNote,
}

export function ArtifactChip({
  artifact,
  onOpen,
  onRemove,
  className,
}: {
  artifact: Artifact
  onOpen: (a: Artifact) => void
  onRemove?: (id: string) => void
  className?: string
}) {
  const Icon = KIND_ICON[artifact.kind]
  return (
    <div
      className={cn(
        "group flex max-w-[16rem] items-center gap-2 rounded-xl border border-border bg-card py-1.5 ps-2 pe-1.5 text-start shadow-sm transition-colors hover:bg-muted",
        className
      )}
    >
      <button
        type="button"
        onClick={() => onOpen(artifact)}
        className="flex min-w-0 flex-1 items-center gap-2 text-start"
        aria-label={`Open ${artifact.name}`}
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground group-hover:bg-background">
          <Icon className="size-4" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-xs font-medium text-foreground">
            {artifact.name}
          </span>
          <span className="block truncate text-[0.7rem] text-muted-foreground">
            {artifactMeta(artifact)}
          </span>
        </span>
      </button>
      {onRemove ? (
        <IconButton
          tooltip="Remove"
          size="icon-xs"
          variant="ghost"
          className="shrink-0 text-muted-foreground"
          onClick={() => onRemove(artifact.id)}
        >
          <X className="size-3.5" />
        </IconButton>
      ) : null}
    </div>
  )
}
