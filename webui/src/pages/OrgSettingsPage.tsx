import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useOrgMembers, useOrgs } from '../api/queries'
import { currentOrgId, currentUsername } from '../api/shell'
import type { OrgRole } from '../api/types'
import { InviteMemberModal } from '../components/InviteMemberModal'
import { MembersTable } from '../components/MembersTable'
import { RoleLegend } from '../components/RoleLegend'
import { useToast } from '../components/toastContext'

export function OrgSettingsPage() {
  const orgs = useOrgs()
  const orgId = currentOrgId()
  const members = useOrgMembers(orgId ?? undefined)
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [inviting, setInviting] = useState(false)

  const org = orgs.data?.find((entry) => entry.id === orgId)
  const canManage = org?.role === 'admin'

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['orgs', orgId, 'members'] })
  }

  async function handleRoleChange(identityId: string, role: OrgRole) {
    if (!orgId) return
    try {
      await api.patch(`/orgs/${orgId}/members/${identityId}`, { role })
      invalidate()
      showToast('Role updated.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  async function handleRemove(identityId: string) {
    if (!orgId) return
    try {
      await api.delete(`/orgs/${orgId}/members/${identityId}`)
      invalidate()
      showToast('Member removed.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  if (!orgId) return <p className="text-sm text-muted-foreground">No active organization.</p>

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Members</h2>
        {canManage && (
          <button
            type="button"
            onClick={() => setInviting(true)}
            className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            Invite member
          </button>
        )}
      </div>
      <p className="mb-6 max-w-xl text-[13.5px] text-muted-foreground">
        Role sets what a member can do; shelf access sets which shelves of documents they can see
        and search. A member with no shelves assigned sees none.
      </p>

      {members.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {members.data && (
        <MembersTable
          orgId={orgId}
          members={members.data}
          canManage={canManage}
          currentUserEmail={currentUsername()}
          onRoleChange={(identityId, role) => void handleRoleChange(identityId, role)}
          onRemove={(identityId) => void handleRemove(identityId)}
        />
      )}

      <div className="mt-8 max-w-md">
        <RoleLegend />
      </div>

      {inviting && (
        <InviteMemberModal
          orgId={orgId}
          onClose={() => setInviting(false)}
          onInvited={() => {
            invalidate()
            setInviting(false)
            showToast('Invite sent.')
          }}
        />
      )}
    </div>
  )
}
