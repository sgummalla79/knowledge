import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useCategories } from '../api/queries'
import type { Category } from '../api/types'
import { CategoryFormModal } from '../components/CategoryFormModal'

export function CategoriesSettingsPage() {
  const categories = useCategories()
  const queryClient = useQueryClient()
  const [editingCategory, setEditingCategory] = useState<Category | null>(null)
  const [creating, setCreating] = useState(false)

  function handleSaved() {
    void queryClient.invalidateQueries({ queryKey: ['categories'] })
    setEditingCategory(null)
    setCreating(false)
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
    </div>
  )
}
