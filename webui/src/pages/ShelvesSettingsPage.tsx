import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useShelves } from '../api/queries'
import type { Shelf } from '../api/types'
import { ShelfFormModal } from '../components/ShelfFormModal'

export function ShelvesSettingsPage() {
  const shelves = useShelves()
  const queryClient = useQueryClient()
  const [editingShelf, setEditingShelf] = useState<Shelf | null>(null)
  const [creating, setCreating] = useState(false)

  function handleSaved() {
    void queryClient.invalidateQueries({ queryKey: ['shelves'] })
    setEditingShelf(null)
    setCreating(false)
  }

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Your shelves</h2>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          New shelf
        </button>
      </div>
      <p className="mb-6 max-w-xl text-[13.5px] text-muted-foreground">
        A shelf groups documents for access control, independent of category. Every document lives
        on at least one shelf; a member sees a document only if they have access to one of its
        shelves.
      </p>

      {shelves.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {shelves.data && shelves.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="pb-2.5 font-semibold">Shelf</th>
                <th className="pb-2.5 font-semibold">Documents</th>
                <th className="pb-2.5 font-semibold">Members with access</th>
                <th className="pb-2.5 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {shelves.data.map((shelf) => (
                <tr key={shelf.id} className="border-t border-border">
                  <td className="py-3.5 pr-4">
                    <div className="font-semibold text-foreground">{shelf.name}</div>
                    {shelf.description && <div className="text-[12.5px] text-muted-foreground">{shelf.description}</div>}
                  </td>
                  <td className="py-3.5 pr-4 text-foreground">{shelf.document_count}</td>
                  <td className="py-3.5 pr-4">
                    <span className="rounded-sm bg-secondary px-2.5 py-0.5 text-xs text-foreground">
                      {shelf.member_count} member{shelf.member_count === 1 ? '' : 's'}
                    </span>
                  </td>
                  <td className="py-3.5 text-right">
                    <button
                      type="button"
                      onClick={() => setEditingShelf(shelf)}
                      className="text-[13px] text-primary hover:underline"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editingShelf) && (
        <ShelfFormModal
          shelf={editingShelf}
          onClose={() => {
            setCreating(false)
            setEditingShelf(null)
          }}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
