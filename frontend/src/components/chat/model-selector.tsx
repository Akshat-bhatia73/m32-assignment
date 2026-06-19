import { Brain, Check, ChevronsUpDown, Cpu } from "lucide-react"
import { Fragment, type ComponentType, useEffect, useMemo } from "react"

import { GoogleIcon, OpenAIIcon } from "@/components/icons/brand-icons"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { ReasoningEffort } from "@/lib/types"
import { cn } from "@/lib/utils"
import { activeModel, activeReasoning, useModelStore } from "@/stores/model-store"

type IconType = ComponentType<{ className?: string }>

const PROVIDER_LABEL: Record<string, string> = { openai: "OpenAI", google: "Google" }
const PROVIDER_ICON: Record<string, IconType> = { openai: OpenAIIcon, google: GoogleIcon }
const PROVIDER_ORDER = ["openai", "google"]
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

const COST_LABEL: Record<number, string> = { 1: "Most economical to run", 2: "Higher running cost" }

/** Relative running cost as 1–N "$" (filled to the model's tier), with an explanatory tooltip. */
function CostTier({ tier, max }: { tier: number; max: number }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span className="font-semibold tracking-tight text-muted-foreground/70">
            {"$".repeat(tier)}
          </span>
        }
      />
      <TooltipContent>{COST_LABEL[tier] ?? `Relative cost ${tier} of ${max}`}</TooltipContent>
    </Tooltip>
  )
}

/** Icon-only marker that a model supports step-by-step reasoning. */
function ReasoningBadge() {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span className="flex items-center text-muted-foreground/70">
            <Brain className="size-3.5" />
          </span>
        }
      />
      <TooltipContent>Supports step-by-step reasoning</TooltipContent>
    </Tooltip>
  )
}

/** Conversation-model picker for the composer. Internal classification stays on a fixed cheap
 * model server-side; this only changes the model that writes the visible reply. */
export function ModelSelector({ disabled }: { disabled?: boolean }) {
  const load = useModelStore((s) => s.load)
  const loaded = useModelStore((s) => s.loaded)
  const models = useModelStore((s) => s.models)
  const defaultModel = useModelStore((s) => s.defaultModel)
  const maxCostTier = useModelStore((s) => s.maxCostTier)
  const setModel = useModelStore((s) => s.setModel)
  const setReasoning = useModelStore((s) => s.setReasoning)
  const current = useModelStore(activeModel)
  const reasoning = useModelStore(activeReasoning)

  useEffect(() => {
    if (!loaded) load()
  }, [loaded, load])

  const groups = useMemo(
    () =>
      PROVIDER_ORDER.map((provider) => ({
        provider,
        items: models.filter((m) => m.provider === provider),
      })).filter((g) => g.items.length > 0),
    [models]
  )

  // Nothing usable (no provider key on the server) — the chat itself won't run either.
  if (loaded && models.length === 0) return null

  const TriggerIcon = current ? PROVIDER_ICON[current.provider] ?? Cpu : Cpu

  const triggerClass =
    "h-8 gap-1.5 rounded-full border border-border/70 bg-muted/50 px-2.5 text-xs font-medium text-foreground hover:bg-muted"

  return (
    <div className="flex items-center gap-1.5">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="sm" disabled={disabled} className={triggerClass}>
              <TriggerIcon className="size-3.5" />
              <span className="max-w-40 truncate">{current?.label ?? "Model"}</span>
              {current ? <CostTier tier={current.cost_tier} max={maxCostTier} /> : null}
              <ChevronsUpDown className="size-3 text-muted-foreground/60" />
            </Button>
          }
        />
        <DropdownMenuContent side="top" align="start" sideOffset={8} className="w-[21rem] p-1.5">
          <p className="px-2.5 pb-1 pt-1.5 text-xs text-muted-foreground">
            Pick the model that writes your replies
          </p>
          {groups.map((group, gi) => {
            const ProviderIcon = PROVIDER_ICON[group.provider] ?? Cpu
            return (
              <Fragment key={group.provider}>
                {gi > 0 ? <DropdownMenuSeparator className="my-1" /> : null}
                <DropdownMenuGroup>
                  <DropdownMenuLabel className="flex items-center gap-2 px-2.5 pb-1 pt-2 text-xs font-medium text-muted-foreground">
                    <ProviderIcon className="size-3.5" />
                    {PROVIDER_LABEL[group.provider] ?? group.provider}
                  </DropdownMenuLabel>
                  {group.items.map((m) => {
                    const selected = current?.id === m.id
                    return (
                      <DropdownMenuItem
                        key={m.id}
                        onClick={() => setModel(m.id)}
                        className={cn(
                          "items-start gap-2.5 rounded-xl px-2.5 py-2",
                          selected && "bg-accent/50"
                        )}
                      >
                        <Check
                          className={cn(
                            "mt-0.5 size-4 shrink-0 text-primary",
                            selected ? "opacity-100" : "opacity-0"
                          )}
                        />
                        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-medium leading-none">{m.label}</span>
                            {m.id === defaultModel ? (
                              <span className="rounded-md bg-foreground/[0.06] px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground">
                                Default
                              </span>
                            ) : null}
                            <span className="ms-auto flex items-center gap-2 ps-2">
                              {m.supports_reasoning ? <ReasoningBadge /> : null}
                              <CostTier tier={m.cost_tier} max={maxCostTier} />
                            </span>
                          </div>
                          <span className="text-xs font-normal leading-snug text-muted-foreground">
                            {m.blurb}
                          </span>
                        </div>
                      </DropdownMenuItem>
                    )
                  })}
                </DropdownMenuGroup>
              </Fragment>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      {current?.supports_reasoning ? (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="sm" disabled={disabled} className={triggerClass}>
                <Brain className="size-3.5 text-muted-foreground" />
                <span>{cap(reasoning ?? "low")}</span>
                <ChevronsUpDown className="size-3 text-muted-foreground/60" />
              </Button>
            }
          />
          <DropdownMenuContent side="top" align="start" sideOffset={8} className="w-48 p-1.5">
            <p className="px-2.5 pb-1 pt-1.5 text-xs text-muted-foreground">Reasoning effort</p>
            {current.reasoning_options.map((effort: ReasoningEffort) => (
              <DropdownMenuItem
                key={effort}
                onClick={() => setReasoning(effort)}
                className={cn(
                  "gap-2.5 rounded-xl px-2.5 py-1.5",
                  reasoning === effort && "bg-accent/50"
                )}
              >
                <Check
                  className={cn(
                    "size-4 text-primary",
                    reasoning === effort ? "opacity-100" : "opacity-0"
                  )}
                />
                <span className="font-medium">{cap(effort)}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </div>
  )
}
