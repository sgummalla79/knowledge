import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DocumentCard } from '../components/DocumentCard'
import { FilterSidebar } from '../components/FilterSidebar'
import { Pagination } from '../components/Pagination'
import { Select } from '../components/Select'
import { useCategories, useDocuments, useShelves } from '../api/queries'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 300

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
  const [titleQueryInput, setTitleQueryInput] = useState('')
  const [titleQuery, setTitleQuery] = useState('')

  useEffect(() => {
    const timeout = setTimeout(() => {
      setTitleQuery(titleQueryInput.trim())
      setOffset(0)
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timeout)
  }, [titleQueryInput])

  const categories = useCategories()
  const shelves = useShelves()
  const documents = useDocuments({
    type: type ?? undefined,
    shelfId: shelfId ?? undefined,
    sort,
    limit: PAGE_SIZE,
    offset,
    q: titleQuery || undefined,
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
          <div className="mb-5 flex items-center justify-between gap-3">
            <input
              value={titleQueryInput}
              onChange={(event) => setTitleQueryInput(event.target.value)}
              placeholder="Search by document title…"
              className="flex-1 rounded-sm border border-border bg-secondary px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Select value={sort} onChange={setSort} options={SORT_OPTIONS} className="shrink-0 px-3 py-1.5 text-[13px]" />
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
