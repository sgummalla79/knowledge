import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useDocumentShelves, useDocumentTags, useShelves, useTags } from '../api/queries'
import type { Category, Document, Tag } from '../api/types'
import { DOCUMENT_TYPES } from '../lib/documentTypes'
import { Select } from './Select'
import { TagPillInput } from './TagPillInput'
import { useToast } from './toastContext'

interface Props {
  document: Document
  categories: Category[]
}

function invalidateDocument(queryClient: ReturnType<typeof useQueryClient>, documentId: string) {
  void queryClient.invalidateQueries({ queryKey: ['document', documentId] })
  void queryClient.invalidateQueries({ queryKey: ['documents'] })
}

export function DocumentOrganizePanel({ document, categories }: Props) {
  const { showToast } = useToast()
  const queryClient = useQueryClient()
  const allShelves = useShelves()
  const documentShelves = useDocumentShelves(document.id)
  const allTags = useTags()
  const documentTags = useDocumentTags(document.id)

  async function saveMetadata(next: { category_id: string | null; type: string }) {
    try {
      await api.patch(`/documents/${document.id}/metadata`, next)
      invalidateDocument(queryClient, document.id)
      showToast('Document updated.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  async function toggleShelf(shelfId: string, assigned: boolean) {
    try {
      if (assigned) {
        await api.delete(`/shelves/${shelfId}/documents/${document.id}`)
      } else {
        await api.post(`/shelves/${shelfId}/documents`, { document_id: document.id })
      }
      void queryClient.invalidateQueries({ queryKey: ['document', document.id, 'shelves'] })
      void queryClient.invalidateQueries({ queryKey: ['shelves'] })
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  async function addTag(tag: Tag) {
    try {
      await api.post(`/documents/${document.id}/tags`, { tag_id: tag.id })
      void queryClient.invalidateQueries({ queryKey: ['document', document.id, 'tags'] })
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  async function removeTag(tagId: string) {
    try {
      await api.delete(`/documents/${document.id}/tags/${tagId}`)
      void queryClient.invalidateQueries({ queryKey: ['document', document.id, 'tags'] })
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  const assignedShelfIds = new Set((documentShelves.data ?? []).map((shelf) => shelf.id))

  return (
    <section className="mt-8">
      <h2 className="mb-4 text-lg font-semibold text-foreground">Organize</h2>
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <span className="mb-1.5 block text-sm text-foreground">Content type</span>
            <Select
              value={document.type}
              options={DOCUMENT_TYPES}
              onChange={(type) => void saveMetadata({ category_id: document.category_id, type })}
              className="w-full px-4 py-2.5 text-[15px]"
            />
          </div>
          <div>
            <span className="mb-1.5 block text-sm text-foreground">Category</span>
            <Select
              value={document.category_id ?? ''}
              options={[{ value: '', label: 'No category' }, ...categories.map((c) => ({ value: c.id, label: c.name }))]}
              onChange={(categoryId) => void saveMetadata({ category_id: categoryId || null, type: document.type })}
              className="w-full px-4 py-2.5 text-[15px]"
            />
          </div>
        </div>

        <div>
          <span className="mb-1.5 block text-sm text-foreground">Shelves — who can retrieve this</span>
          {(allShelves.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No shelves yet.</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {(allShelves.data ?? []).map((shelf) => (
                <label key={shelf.id} className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={assignedShelfIds.has(shelf.id)}
                    onChange={() => void toggleShelf(shelf.id, assignedShelfIds.has(shelf.id))}
                    className="accent-primary"
                  />
                  {shelf.name}
                </label>
              ))}
            </div>
          )}
        </div>

        <div>
          <span className="mb-1.5 block text-sm text-foreground">Tags</span>
          <TagPillInput
            tags={documentTags.data ?? []}
            existingTags={allTags.data ?? []}
            onAdd={addTag}
            onRemove={removeTag}
            placeholder="e.g. billing, faq — press Tab or Enter"
          />
        </div>
      </div>
    </section>
  )
}
