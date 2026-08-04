import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useCreateLibrary, useDeleteLibrary, useLibraries, useUpdateLibrary } from '../api/queries'
import { LibraryIcon, PlusIcon } from './icons'
import { LibraryFormModal } from './LibraryFormModal'
import { LibraryItemMenu } from './LibraryItemMenu'
import { AccountMenu } from './AccountMenu'
import { useToast } from './toastContext'
import type { Library } from '../api/types'

export interface WorkspaceContext {
  openCreateLibrary: () => void
}

export function Layout() {
  const { showToast } = useToast()
  const { data: libraries } = useLibraries()
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams<{ libraryId?: string }>()
  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState<Library | null>(null)

  const createLibrary = useCreateLibrary()
  const updateLibrary = useUpdateLibrary(editing?.id ?? '')
  const deleteLibrary = useDeleteLibrary()

  function handleDelete(library: Library) {
    if (!window.confirm(`Delete "${library.name}"? This also deletes its documents.`)) return
    deleteLibrary.mutate(library.id, {
      onSuccess: () => {
        if (params.libraryId === library.id) navigate('/workspace')
      },
      onError: (error) => showToast(error.message),
    })
  }

  return (
    <div className="shell">
      <aside className="rail">
        <a href="/workspace" className="rail-brand">
          <img src="/static/brand-icon.png" alt="" />
          <span>Knowledge</span>
        </a>
        <div className="rail-header">
          <div className="rail-header-row">
            <h2>
              <Link to="/workspace" className={`rail-header-link ${location.pathname === '/workspace' ? 'active' : ''}`}>
                <LibraryIcon />
                Libraries
              </Link>
            </h2>
            <button type="button" className="icon-btn" onClick={() => setCreateOpen(true)} aria-label="New library">
              <PlusIcon />
            </button>
          </div>
        </div>
        <nav className="rail-list rail-list-tree">
          {(libraries ?? []).map((library) => (
            <Link key={library.id} to={`/workspace/libraries/${library.id}`} className={`rail-item ${params.libraryId === library.id ? 'active' : ''}`}>
              <LibraryIcon />
              <span>{library.name}</span>
              <LibraryItemMenu onRename={() => setEditing(library)} onDelete={() => handleDelete(library)} />
            </Link>
          ))}
        </nav>
        <div className="rail-footer">
          <AccountMenu />
        </div>
      </aside>
      <div className="main">
        <Outlet context={{ openCreateLibrary: () => setCreateOpen(true) } satisfies WorkspaceContext} />
      </div>

      {createOpen && (
        <LibraryFormModal
          title="New library"
          submitLabel="Create"
          pending={createLibrary.isPending}
          onClose={() => {
            setCreateOpen(false)
            createLibrary.reset()
          }}
          onSubmit={(values) =>
            createLibrary.mutate(values, {
              onSuccess: (library) => {
                setCreateOpen(false)
                navigate(`/workspace/libraries/${library.id}`)
              },
              onError: (error) => showToast(error.message),
            })
          }
        />
      )}

      {editing && (
        <LibraryFormModal
          title="Rename library"
          submitLabel="Save"
          initial={editing}
          pending={updateLibrary.isPending}
          onClose={() => {
            setEditing(null)
            updateLibrary.reset()
          }}
          onSubmit={(values) =>
            updateLibrary.mutate(values, {
              onSuccess: () => setEditing(null),
              onError: (error) => showToast(error.message),
            })
          }
        />
      )}
    </div>
  )
}
