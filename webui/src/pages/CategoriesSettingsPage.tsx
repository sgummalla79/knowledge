import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useCategories } from '../api/queries'
import type { Category } from '../api/types'
import { CategoryFormModal } from '../components/CategoryFormModal'
import { DeleteWithDocumentsModal } from '../components/DeleteWithDocumentsModal'
import { useToast } from '../components/toastContext'

export function CategoriesSettingsPage() {
  const { showToast } = useToast()
  const categories = useCategories()
  const queryClient = useQueryClient()
  const [editingCategory, setEditingCategory] = useState<Category | null>(null)
  const [creating, setCreating] = useState(false)
  const [countingDeleteId, setCountingDeleteId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<{ category: Category; documentCount: number } | null>(null)

  function handleSaved() {
    void queryClient.invalidateQueries({ queryKey: ['categories'] })
    setEditingCategory(null)
    setCreating(false)
  }

  async function handleDeleteClick(category: Category) {
    setCountingDeleteId(category.id)
    try {
      // Category has no document_count of its own (unlike Shelf) -- the total-count header off
      // the existing documents list endpoint gives an accurate number without a backend change,
      // fetched only once the user actually asks to delete, not for every row up front.
      const { total } = await api.getPaginated(`/documents?category_id=${category.id}&limit=1`)
      setDeleting({ category, documentCount: total })
    } catch {
      showToast("Couldn't check this category's documents — please try again.", 'error')
    } finally {
      setCountingDeleteId(null)
    }
  }

  function handleDeleted(documentsDeleted: number) {
    void queryClient.invalidateQueries({ queryKey: ['categories'] })
    if (documentsDeleted > 0) {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    }
    showToast(
      documentsDeleted > 0
        ? `Category deleted — ${documentsDeleted} document${documentsDeleted === 1 ? '' : 's'} permanently deleted.`
        : 'Category deleted.',
    )
    setDeleting(null)
  }

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Data categories</h2>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          New category
        </button>
      </div>
      <p className="mb-6 max-w-xl text-[13.5px] text-muted-foreground">
        A category groups documents by subject — independent of shelves, which control access.
        Every document belongs to at most one category; queries with no category selected are
        routed to the closest match by description.
      </p>

      {categories.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {categories.data && categories.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="pb-2.5 font-semibold">Category</th>
                <th className="pb-2.5 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {categories.data.map((category) => (
                <tr key={category.id} className="border-t border-border">
                  <td className="py-3.5 pr-4">
                    <div className="font-semibold text-foreground">{category.name}</div>
                    {category.description && (
                      <div className="text-[12.5px] text-muted-foreground">{category.description}</div>
                    )}
                  </td>
                  <td className="py-3.5 text-right">
                    <button
                      type="button"
                      onClick={() => setEditingCategory(category)}
                      className="text-[13px] text-primary hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteClick(category)}
                      disabled={countingDeleteId === category.id}
                      className="ml-4 text-[13px] text-destructive hover:underline disabled:opacity-60"
                    >
                      {countingDeleteId === category.id ? 'Checking…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {categories.data && categories.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No categories yet.</p>
      )}

      {(creating || editingCategory) && (
        <CategoryFormModal
          category={editingCategory}
          onClose={() => {
            setCreating(false)
            setEditingCategory(null)
          }}
          onSaved={handleSaved}
        />
      )}

      {deleting && (
        <DeleteWithDocumentsModal
          kind="category"
          name={deleting.category.name}
          documentCount={deleting.documentCount}
          deletePath={`/categories/${deleting.category.id}`}
          onClose={() => setDeleting(null)}
          onDeleted={handleDeleted}
        />
      )}
    </div>
  )
}
