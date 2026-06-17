import type { DynamicToolUIPart, ToolUIPart } from "ai"

import { Tool, ToolContent, ToolHeader, ToolInput, ToolOutput } from "@/components/ai-elements/tool"

const TITLES: Record<string, string> = {
  extract_action_items: "Reading the notes",
}

function titleFor(toolName: string): string {
  return TITLES[toolName] ?? toolName.replace(/_/g, " ")
}

export function ToolPartView({ part }: { part: ToolUIPart | DynamicToolUIPart }) {
  const toolName = part.type === "dynamic-tool" ? part.toolName : part.type.replace(/^tool-/, "")
  const title = titleFor(toolName)

  return (
    <Tool>
      {part.type === "dynamic-tool" ? (
        <ToolHeader type="dynamic-tool" state={part.state} toolName={toolName} title={title} />
      ) : (
        <ToolHeader type={part.type} state={part.state} title={title} />
      )}
      <ToolContent>
        <ToolInput input={part.input} />
        <ToolOutput output={part.output} errorText={part.errorText} />
      </ToolContent>
    </Tool>
  )
}
