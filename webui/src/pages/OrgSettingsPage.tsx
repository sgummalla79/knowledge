import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useOrgMembers, useOrgs } from '../api/queries'
import { currentOrgId, currentUsername } from '../api/shell'
import { InviteMemberModal } from '../components/InviteMemberModal'
import { MembersTable } from '../components/MembersTable'
import { useToast } from '../components/toastContext'

export function OrgSettingsPage() {
  const orgs = useOrgs()
  const orgId = currentOrgId()
  const members = useOrgMembers(orgId ?? undefined)
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [inviting, setInviting] = useState(false)

  const org = orgs.data?.find((entry) => entry.id === orgId)
  const canManage = org?.permissions.includes('org_members:write') ?? false

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['orgs', orgId, 'members'] })
  }

  async function handleProfileChange(identityId: string, profileId: string) {
    if (!orgId) return
    try {
      await api.patch(`/orgs/${orgId}/members/${identityId}`, { profile_id: profileId })
      invalidate()
      showToast('Profile updated.')
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
        A member's profile sets what they can do; shelf access sets which shelves of documents
        they can see and search. A member with no shelves assigned sees none.{' '}
        {canManage && (
          <Link to="/org/profiles" className="text-foreground underline">
            Manage profiles
          </Link>
        )}
      </p>

      {members.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {members.data && (
        <MembersTable
          orgId={orgId}
          members={members.data}
          canManage={canManage}
          currentUserEmail={currentUsername()}
          onProfileChange={(identityId, profileId) => void handleProfileChange(identityId, profileId)}
          onRemove={(identityId) => void handleRemove(identityId)}
        />
      )}

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
