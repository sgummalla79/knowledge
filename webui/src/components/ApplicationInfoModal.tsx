import { Modal } from './Modal'
import { useScopeGroups } from '../api/applicationQueries'
import type { Application } from '../api/types'

interface Props {
  application: Application
  onClose: () => void
}

export function ApplicationInfoModal({ application, onClose }: Props) {
  const { data: scopeGroups } = useScopeGroups()

  // Buckets this application's allowed_scopes under the server's canonical resource-group
  // headings (GET /dashboard/scopes) rather than re-deriving the grouping client-side.
  const groups = (scopeGroups ?? [])
    .map((group) => ({ label: group.label, scopes: group.scopes.filter((scope) => application.allowed_scopes.includes(scope)) }))
    .filter((group) => group.scopes.length > 0)

  return (
    <Modal title={application.name} onClose={onClose} wide>
      <p className="popup-field">
        <strong>Client Id</strong>
        <br />
        <code>{application.id}</code>
      </p>
      <p className="popup-field">
        <strong>Client Secret</strong>
        <br />
        <span className="popup-hint">Hidden — only shown once, at registration.</span>
      </p>
      <p className="popup-field">
        <strong>Allowed scopes</strong>
      </p>
      <div className="scope-groups-grid">
        {groups.map((group) => (
          <div key={group.label} className="scope-group">
            <div className="scope-group-label">{group.label}</div>
            <ul className="scope-view-list">
              {group.scopes.map((scope) => (
                <li key={scope}>{scope}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  )
}
