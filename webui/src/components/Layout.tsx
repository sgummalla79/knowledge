import { useState } from 'react'
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom'
import { useCreateLibrary, useDeleteLibrary, useLibraries, useUpdateLibrary } from '../api/queries'
import { FolderIcon, PencilIcon, PlusIcon, TrashIcon } from './icons'
import { LibraryFormModal } from './LibraryFormModal'
import { AccountMenu } from './AccountMenu'
import type { Library } from '../api/types'

export function Layout() {
  const { data: libraries } = useLibraries()
  const navigate = useNavigate()
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
        if (params.libraryId === library.id) navigate('/')
      },
    })
  }

  return (
    <div className="shell">
      <aside className="rail">
        <a href="/dashboard" className="rail-brand">
          <img src="/static/brand-icon.png" alt="" />
          <span>Knowledge</span>
        </a>
        <div className="rail-header">
          <h2>Libraries</h2>
          <button type="button" className="icon-btn" onClick={() => setCreateOpen(true)} aria-label="New library">
            <PlusIcon />
          </button>
        </div>
        <nav className="rail-list">
          {(libraries ?? []).map((library) => (
            <Link key={library.id} to={`/libraries/${library.id}`} className={`rail-item ${params.libraryId === library.id ? 'active' : ''}`}>
              <FolderIcon />
              <span>{library.name}</span>
              <span className="rail-item-actions">
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Rename library"
                  onClick={(event) => {
                    event.preventDefault()
                    setEditing(library)
                  }}
                >
                  <PencilIcon />
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Delete library"
                  onClick={(event) => {
                    event.preventDefault()
                    handleDelete(library)
                  }}
                >
                  <TrashIcon />
                </button>
              </span>
            </Link>
          ))}
        </nav>
        <div className="rail-footer">
          <AccountMenu />
        </div>
      </aside>
      <div className="main">
        <Outlet />
      </div>

      {createOpen && (
        <LibraryFormModal
          title="New library"
          submitLabel="Create"
          pending={createLibrary.isPending}
          error={createLibrary.error?.message}
          onClose={() => {
            setCreateOpen(false)
            createLibrary.reset()
          }}
          onSubmit={(values) =>
            createLibrary.mutate(values, {
              onSuccess: () => setCreateOpen(false),
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
          error={updateLibrary.error?.message}
          onClose={() => {
            setEditing(null)
            updateLibrary.reset()
          }}
          onSubmit={(values) =>
            updateLibrary.mutate(values, {
              onSuccess: () => setEditing(null),
            })
          }
        />
      )}
    </div>
  )
}
