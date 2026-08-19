import { useQueries } from '@tanstack/react-query'
import { api } from '../api/client'
import type { OrgMember, OrgRole, Shelf } from '../api/types'

interface Props {
  orgId: string
  members: OrgMember[]
  canManage: boolean
  currentUserEmail: string
  onRoleChange: (identityId: string, role: OrgRole) => void
  onRemove: (identityId: string) => void
}

export function MembersTable({ orgId, members, canManage, currentUserEmail, onRoleChange, onRemove }: Props) {
  const shelfAccess = useQueries({
    queries: members.map((member) => ({
      queryKey: ['orgs', orgId, 'members', member.identity_id, 'shelf-access'],
      queryFn: () => api.get<Shelf[]>(`/orgs/${orgId}/members/${member.identity_id}/shelf-access`),
      enabled: canManage,
    })),
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="pb-2.5 font-semibold">Member</th>
            <th className="pb-2.5 font-semibold">Role</th>
            <th className="pb-2.5 font-semibold">Shelf access</th>
            <th className="pb-2.5 font-semibold"></th>
          </tr>
        </thead>
        <tbody>
          {members.map((member, index) => {
            const shelves = shelfAccess[index]?.data ?? []
            const isSelf = member.email === currentUserEmail
            return (
              <tr key={member.identity_id} className="border-t border-border">
                <td className="py-3.5 pr-4">
                  <div className="font-semibold text-foreground">{member.name}</div>
                  <div className="text-[12.5px] text-muted-foreground">{member.email}</div>
                </td>
                <td className="py-3.5 pr-4">
                  <select
                    value={member.role}
                    disabled={!canManage || isSelf}
                    onChange={(event) => onRoleChange(member.identity_id, event.target.value as OrgRole)}
                    className="rounded-sm border border-border bg-secondary px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-60"
                  >
                    <option value="admin">Admin</option>
                    <option value="contributor">Contributor</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </td>
                <td className="py-3.5 pr-4">
                  {member.role === 'admin' ? (
                    <span className="rounded-sm bg-accent px-2.5 py-0.5 text-xs text-accent-foreground">All shelves</span>
                  ) : shelves.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {shelves.map((shelf) => (
                        <span key={shelf.id} className="rounded-sm bg-secondary px-2.5 py-0.5 text-xs text-foreground">
                          {shelf.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">No shelves</span>
                  )}
                </td>
                <td className="py-3.5 text-right">
                  {canManage && !isSelf && (
                    <button
                      type="button"
                      onClick={() => onRemove(member.identity_id)}
                      className="text-[13px] text-destructive hover:underline"
                    >
                      Remove
                    </button>
                  )}
                  {isSelf && <span className="text-[13px] text-muted-foreground">You</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
