import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DocumentCard } from '../components/DocumentCard'
import { FilterSidebar } from '../components/FilterSidebar'
import { Pagination } from '../components/Pagination'
import { useCategories, useDocuments, useShelves } from '../api/queries'

const PAGE_SIZE = 12

const SORT_OPTIONS = [
  { value: '-created_at', label: 'Recently updated' },
  { value: 'title', label: 'A–Z' },
]

export function BrowsePage() {
  const [searchParams] = useSearchParams()
  const [type, setType] = useState<string | null>(searchParams.get('type'))
  const [shelfId, setShelfId] = useState<string | null>(null)
  const [sort, setSort] = useState('-created_at')
  const [offset, setOffset] = useState(0)

  const categories = useCategories()
  const shelves = useShelves()
  const documents = useDocuments({
    type: type ?? undefined,
    shelfId: shelfId ?? undefined,
    sort,
    limit: PAGE_SIZE,
    offset,
  })

  function updateFilter(setter: (value: string | null) => void, value: string | null) {
    setter(value)
    setOffset(0)
  }

  return (
    <div className="py-12">
      <h1 className="mb-1 text-[32px] font-semibold text-foreground">Browse the library</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        {documents.data ? `${documents.data.total} items indexed and ready for retrieval.` : 'Loading…'}
      </p>

      <div className="flex gap-10">
        <FilterSidebar
          categories={categories.data ?? []}
          shelves={shelves.data ?? []}
          selectedType={type}
          selectedShelfId={shelfId}
          onTypeChange={(value) => updateFilter(setType, value)}
          onShelfChange={(value) => updateFilter(setShelfId, value)}
        />

        <div className="flex-1">
          <div className="mb-5 flex justify-end">
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value)}
              className="rounded-sm border border-border bg-secondary px-3 py-1.5 text-[13px] text-foreground"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {documents.isLoading && <p className="text-sm text-muted-foreground">Loading documents…</p>}
          {documents.isError && (
            <p className="text-sm text-destructive">Couldn&apos;t load documents — try again.</p>
          )}
          {documents.data && documents.data.items.length === 0 && (
            <p className="rounded-sm bg-card p-8 text-center text-sm text-muted-foreground">
              No documents match these filters.
            </p>
          )}
          {documents.data && documents.data.items.length > 0 && (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {documents.data.items.map((document) => (
                <DocumentCard key={document.id} document={document} />
              ))}
            </div>
          )}

          {documents.data && (
            <Pagination offset={offset} limit={PAGE_SIZE} total={documents.data.total} onOffsetChange={setOffset} />
          )}
        </div>
      </div>
    </div>
  )
}
