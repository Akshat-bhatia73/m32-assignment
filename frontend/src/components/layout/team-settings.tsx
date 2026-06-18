import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Crown, Pencil, Send, Trash2, UserPlus, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { IconButton } from "@/components/ui/icon-button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { api, ApiError } from "@/lib/api"
import type { Org } from "@/lib/types"

export function TeamSettings({ open }: { open: boolean }) {
  const queryClient = useQueryClient()
  const orgQuery = useQuery({ queryKey: ["org"], queryFn: api.getOrg, enabled: open })
  const org = orgQuery.data

  const setOrg = (next: Org) => queryClient.setQueryData(["org"], next)

  if (orgQuery.isLoading || !org) {
    return (
      <div className="flex justify-center py-6">
        <Spinner className="size-5 text-muted-foreground" />
      </div>
    )
  }

  const isOwner = org.role === "owner"
  const used = org.members.length + org.invites.length
  const atCap = used >= org.member_cap

  return (
    <section className="space-y-4">
      <OrgName org={org} isOwner={isOwner} onSaved={setOrg} />

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-foreground">Members</h3>
          <span className="text-xs text-muted-foreground">
            {used} of {org.member_cap}
          </span>
        </div>
        <ul className="space-y-1.5">
          {org.members.map((m) => (
            <li
              key={m.id}
              className="flex items-center gap-3 rounded-xl border border-border bg-card p-2.5"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium uppercase text-muted-foreground">
                {(m.name || m.email).charAt(0)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {m.name || m.email}
                </p>
                {m.name ? (
                  <p className="truncate text-xs text-muted-foreground">{m.email}</p>
                ) : null}
              </div>
              {m.role === "owner" ? (
                <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground">
                  <Crown className="size-3.5" />
                  Owner
                </span>
              ) : isOwner ? (
                <RemoveMember id={m.id} label={m.name || m.email} onDone={setOrg} />
              ) : (
                <span className="shrink-0 text-xs text-muted-foreground">Member</span>
              )}
            </li>
          ))}
        </ul>
      </div>

      {org.invites.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-foreground">Pending invites</h3>
          <ul className="space-y-1.5">
            {org.invites.map((inv) => (
              <li
                key={inv.id}
                className="flex items-center gap-3 rounded-xl border border-dashed border-border p-2.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-foreground">{inv.name || inv.email}</p>
                  {inv.name ? (
                    <p className="truncate text-xs text-muted-foreground">{inv.email}</p>
                  ) : null}
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">Invited</span>
                {isOwner ? <RevokeInvite id={inv.id} onDone={setOrg} /> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isOwner ? <InviteForm atCap={atCap} onInvited={setOrg} /> : null}
    </section>
  )
}

function OrgName({
  org,
  isOwner,
  onSaved,
}: {
  org: Org
  isOwner: boolean
  onSaved: (org: Org) => void
}) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(org.name)
  const save = useMutation({
    mutationFn: () => api.renameOrg(name.trim()),
    onSuccess: (next) => {
      onSaved(next)
      setEditing(false)
      toast.success("Workspace renamed")
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Couldn't rename"),
  })

  if (!isOwner) {
    return (
      <div>
        <p className="text-xs text-muted-foreground">Workspace</p>
        <p className="text-base font-semibold text-foreground">{org.name}</p>
      </div>
    )
  }

  return (
    <div>
      <p className="text-xs text-muted-foreground">Workspace</p>
      {editing ? (
        <div className="mt-1 flex items-center gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          <IconButton
            tooltip="Save"
            size="icon-sm"
            disabled={!name.trim() || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? <Spinner className="size-4" /> : <Check className="size-4" />}
          </IconButton>
          <IconButton
            tooltip="Cancel"
            size="icon-sm"
            variant="ghost"
            onClick={() => {
              setName(org.name)
              setEditing(false)
            }}
          >
            <X className="size-4" />
          </IconButton>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <p className="text-base font-semibold text-foreground">{org.name}</p>
          <IconButton
            tooltip="Rename workspace"
            size="icon-xs"
            variant="ghost"
            className="text-muted-foreground"
            onClick={() => setEditing(true)}
          >
            <Pencil className="size-3.5" />
          </IconButton>
        </div>
      )}
    </div>
  )
}

function InviteForm({ atCap, onInvited }: { atCap: boolean; onInvited: (org: Org) => void }) {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const invite = useMutation({
    mutationFn: () => api.createInvite({ email: email.trim(), name: name.trim() || undefined }),
    onSuccess: (next) => {
      onInvited(next)
      setName("")
      setEmail("")
      toast.success("Invite sent", { description: "We emailed them a link to join." })
    },
    onError: (err) =>
      toast.error("Couldn't send invite", {
        description: err instanceof ApiError ? err.message : "Please try again.",
      }),
  })

  return (
    <form
      className="space-y-2 rounded-xl border border-border bg-card p-3"
      onSubmit={(e) => {
        e.preventDefault()
        if (email.trim()) invite.mutate()
      }}
    >
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <UserPlus className="size-4" />
        Invite a teammate
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          placeholder="Name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="sm:flex-1"
        />
        <Input
          type="email"
          placeholder="teammate@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="sm:flex-1"
        />
      </div>
      <Button
        type="submit"
        size="sm"
        className="w-full sm:w-auto"
        disabled={!email.trim() || atCap || invite.isPending}
      >
        {invite.isPending ? <Spinner className="size-4" /> : <Send className="size-4" />}
        {atCap ? "Workspace full" : "Send invite"}
      </Button>
    </form>
  )
}

function RemoveMember({
  id,
  label,
  onDone,
}: {
  id: string
  label: string
  onDone: (org: Org) => void
}) {
  const mut = useMutation({
    mutationFn: () => api.removeMember(id),
    onSuccess: (next) => {
      onDone(next)
      toast.success(`Removed ${label}`)
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Couldn't remove"),
  })
  return (
    <IconButton
      tooltip="Remove member"
      size="icon-sm"
      variant="ghost"
      className="text-muted-foreground"
      disabled={mut.isPending}
      onClick={() => mut.mutate()}
    >
      {mut.isPending ? <Spinner className="size-4" /> : <Trash2 className="size-4" />}
    </IconButton>
  )
}

function RevokeInvite({ id, onDone }: { id: string; onDone: (org: Org) => void }) {
  const mut = useMutation({
    mutationFn: () => api.revokeInvite(id),
    onSuccess: (next) => {
      onDone(next)
      toast.success("Invite revoked")
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Couldn't revoke"),
  })
  return (
    <IconButton
      tooltip="Revoke invite"
      size="icon-sm"
      variant="ghost"
      className="text-muted-foreground"
      disabled={mut.isPending}
      onClick={() => mut.mutate()}
    >
      {mut.isPending ? <Spinner className="size-4" /> : <X className="size-4" />}
    </IconButton>
  )
}
