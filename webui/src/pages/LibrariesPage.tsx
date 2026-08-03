import { useNavigate } from 'react-router-dom'
import { useLibraries } from '../api/queries'
import { FolderIcon } from '../components/icons'

export function LibrariesPage() {
  const { data: libraries, isLoading } = useLibraries()
  const navigate = useNavigate()

  return (
    <>
      <h1>Knowledge</h1>
      <p className="subtitle">Create knowledge libraries and upload documents.</p>

      {isLoading && <p className="subtitle">Loading…</p>}

      {!isLoading && (libraries ?? []).length === 0 && (
        <div className="empty-state">No libraries yet — use the + button to create one.</div>
      )}

      <div className="card-grid">
        {(libraries ?? []).map((library) => (
          <div key={library.id} className="library-card" onClick={() => navigate(`/libraries/${library.id}`)}>
            <div className="library-card-icon">
              <FolderIcon />
            </div>
            <div className="library-card-body">
              <h3>{library.name}</h3>
              {library.description && <p>{library.description}</p>}
            </div>
            <span className="badge">{library.document_count} docs</span>
          </div>
        ))}
      </div>
    </>
  )
}
