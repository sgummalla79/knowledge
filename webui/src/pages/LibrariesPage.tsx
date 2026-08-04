import { useMemo, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { useLibraries } from '../api/queries'
import { LibraryIcon, PlusIcon, SearchIcon } from '../components/icons'
import type { WorkspaceContext } from '../components/Layout'

export function LibrariesPage() {
  const { data: libraries, isLoading } = useLibraries()
  const navigate = useNavigate()
  const { openCreateLibrary } = useOutletContext<WorkspaceContext>()
  const [query, setQuery] = useState('')

  const filteredLibraries = useMemo(() => {
    const trimmed = query.trim().toLowerCase()
    if (!trimmed) return libraries ?? []
    return (libraries ?? []).filter((library) => library.name.toLowerCase().includes(trimmed))
  }, [libraries, query])

  return (
    <div className="settings-narrow">
      <div className="page-header">
        <div className="page-header-left">
          <div className="page-header-icon">
            <LibraryIcon />
          </div>
          <div>
            <h1>Libraries</h1>
            <p className="subtitle">Create knowledge libraries and upload documents.</p>
          </div>
        </div>
        <button type="button" onClick={openCreateLibrary}>
          <PlusIcon />
          New Library
        </button>
      </div>

      <div className="search-bar">
        <input
          type="text"
          placeholder="Search libraries…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search libraries"
        />
        <SearchIcon />
      </div>

      {isLoading && <p className="subtitle">Loading…</p>}

      {!isLoading && filteredLibraries.length === 0 && (
        <div className="empty-state">
          {query.trim() ? 'No libraries match your search.' : 'No libraries yet — use the + button to create one.'}
        </div>
      )}

      <div className="card-grid">
        {filteredLibraries.map((library) => (
          <div key={library.id} className="library-card" onClick={() => navigate(`/workspace/libraries/${library.id}`)}>
            <div className="library-card-icon">
              <LibraryIcon />
            </div>
            <div className="library-card-body">
              <h3>{library.name}</h3>
              {library.description && <p>{library.description}</p>}
            </div>
            <span className="badge">{library.document_count} docs</span>
          </div>
        ))}
      </div>
    </div>
  )
}
