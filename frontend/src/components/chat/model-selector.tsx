import { Check, ChevronDown, Gauge, Sparkles } from "lucide-react"
import { Fragment, useEffect, useMemo } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { ReasoningEffort } from "@/lib/types"
import { cn } from "@/lib/utils"
import { activeModel, activeReasoning, useModelStore } from "@/stores/model-store"

const PROVIDER_LABEL: Record<string, string> = { openai: "OpenAI", google: "Google" }
const PROVIDER_ORDER = ["openai", "google"]
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** Conversation-model picker for the composer. Internal classification stays on a fixed cheap
 * model server-side; this only changes the model that writes the visible reply. */
export function ModelSelector({ disabled }: { disabled?: boolean }) {
  const load = useModelStore((s) => s.load)
  const loaded = useModelStore((s) => s.loaded)
  const models = useModelStore((s) => s.models)
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

  return (
    <div className="flex items-center gap-1">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="sm"
              disabled={disabled}
              className="h-8 gap-1.5 rounded-full px-2.5 text-xs text-muted-foreground hover:text-foreground"
            >
              <Sparkles className="size-3.5 text-primary" />
              <span className="max-w-40 truncate font-medium">{current?.label ?? "Model"}</span>
              <ChevronDown className="size-3.5 opacity-60" />
            </Button>
          }
        />
        <DropdownMenuContent align="start" className="w-72">
          {groups.map((group, gi) => (
            <Fragment key={group.provider}>
              {gi > 0 ? <DropdownMenuSeparator /> : null}
              <DropdownMenuLabel>{PROVIDER_LABEL[group.provider] ?? group.provider}</DropdownMenuLabel>
              {group.items.map((m) => (
                <DropdownMenuItem
                  key={m.id}
                  onClick={() => setModel(m.id)}
                  className="items-start gap-2.5 py-2"
                >
                  <Check
                    className={cn(
                      "mt-0.5 size-4 shrink-0 text-primary",
                      current?.id === m.id ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium leading-none">{m.label}</span>
                    <span className="text-xs font-normal text-muted-foreground">{m.blurb}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </Fragment>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {current?.supports_reasoning ? (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled}
                className="h-8 gap-1.5 rounded-full px-2.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <Gauge className="size-3.5" />
                <span className="font-medium">{cap(reasoning ?? "low")}</span>
                <ChevronDown className="size-3.5 opacity-60" />
              </Button>
            }
          />
          <DropdownMenuContent align="start" className="w-44">
            <DropdownMenuLabel>Reasoning effort</DropdownMenuLabel>
            {current.reasoning_options.map((effort: ReasoningEffort) => (
              <DropdownMenuItem key={effort} onClick={() => setReasoning(effort)}>
                <Check
                  className={cn(
                    "size-4 text-primary",
                    reasoning === effort ? "opacity-100" : "opacity-0"
                  )}
                />
                {cap(effort)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </div>
  )
}
