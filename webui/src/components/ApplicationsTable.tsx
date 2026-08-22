import type { Application, OrgMember } from '../api/types'

const AUTH_METHOD_LABELS: Record<string, string> = {
  oauth_client_credentials: 'OAuth 2.0 (client credentials)',
  oauth_authorization_code: 'OAuth 2.0 (authorization code)',
  certificate: 'Certificate',
}

interface Props {
  applications: Application[]
  members: OrgMember[]
  canManage: boolean
  onRotateKey: (application: Application) => void
  onRevoke: (application: Application) => void
  onDelete: (application: Application) => void
}

export function ApplicationsTable({ applications, members, canManage, onRotateKey, onRevoke, onDelete }: Props) {
  function executeAsLabel(application: Application): string | null {
    if (!application.execute_as_identity_id) return null
    const member = members.find((entry) => entry.identity_id === application.execute_as_identity_id)
    return member ? `${member.name} (${member.username})` : application.execute_as_identity_id
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="pb-2.5 font-semibold">Application</th>
            <th className="pb-2.5 font-semibold">Auth method</th>
            <th className="pb-2.5 font-semibold">Access</th>
            <th className="pb-2.5 font-semibold">Status</th>
            <th className="pb-2.5 font-semibold"></th>
          </tr>
        </thead>
        <tbody>
          {applications.map((application) => (
            <tr key={application.id} className="border-t border-border align-top">
              <td className="py-3.5 pr-4">
                <div className="font-semibold text-foreground">{application.name}</div>
                {application.description && (
                  <div className="max-w-xs text-[12.5px] text-muted-foreground">{application.description}</div>
                )}
              </td>
              <td className="py-3.5 pr-4 text-[13px] text-foreground">
                {AUTH_METHOD_LABELS[application.auth_method] ?? application.auth_method}
              </td>
              <td className="py-3.5 pr-4">
                {application.auth_method === 'oauth_authorization_code' ? (
                  <div className="max-w-xs text-[12.5px] text-foreground">Any org member (via consent)</div>
                ) : (
                  <div className="max-w-xs text-[12.5px] text-foreground">
                    Acts as <span className="font-semibold">{executeAsLabel(application)}</span>
                  </div>
                )}
              </td>
              <td className="py-3.5 pr-4">
                <span
                  className={`rounded-sm px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${
                    application.status === 'active' ? 'bg-accent text-accent-foreground' : 'bg-destructive/15 text-destructive'
                  }`}
                >
                  {application.status}
                </span>
              </td>
              <td className="py-3.5 text-right">
                {canManage && application.status === 'active' && (
                  <div className="flex justify-end gap-3">
                    {application.auth_method !== 'oauth_authorization_code' && (
                      <button
                        type="button"
                        onClick={() => onRotateKey(application)}
                        className="text-[13px] text-foreground/80 hover:underline"
                      >
                        Rotate secret
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onRevoke(application)}
                      className="text-[13px] text-destructive hover:underline"
                    >
                      Revoke
                    </button>
                  </div>
                )}
                {canManage && application.status === 'revoked' && (
                  <button
                    type="button"
                    onClick={() => onDelete(application)}
                    className="text-[13px] text-destructive hover:underline"
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
