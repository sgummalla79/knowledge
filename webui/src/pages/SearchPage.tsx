import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { RoutedChunk } from '../api/types'
import { SearchIcon } from '../components/icons'
import { SearchResultRow } from '../components/SearchResultRow'
import { TypeFilterPills } from '../components/TypeFilterPills'

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') ?? ''
  const [input, setInput] = useState(initialQuery)
  const [type, setType] = useState<string | null>(null)
  const [results, setResults] = useState<RoutedChunk[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const q = searchParams.get('q')
    if (!q) return
    setLoading(true)
    setError(null)
    api
      .post<{ chunks: RoutedChunk[] }>('/query', { query: q, top_k: 20 })
      .then((response) => setResults(response.chunks))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Search failed — please try again.'))
      .finally(() => setLoading(false))
  }, [searchParams])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (input.trim()) setSearchParams({ q: input.trim() })
  }

  const query = searchParams.get('q') ?? ''
  const filtered = type ? (results ?? []).filter((result) => result.document_type === type) : results ?? []

  return (
    <div className="py-12">
      <form onSubmit={handleSubmit} className="mb-6 flex max-w-xl gap-2.5">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Search articles, documents…"
          className="flex-1 rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          className="flex items-center gap-2 rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90"
        >
          <SearchIcon /> Search
        </button>
      </form>

      {query && <TypeFilterPills selected={type} onChange={setType} />}

      {loading && <p className="text-sm text-muted-foreground">Searching…</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && results && (
        <>
          <p className="mb-5 text-sm text-muted-foreground">
            {filtered.length} result{filtered.length === 1 ? '' : 's'} for &quot;{query}&quot;
          </p>
          {filtered.length === 0 ? (
            <p className="rounded-sm bg-card p-8 text-center text-sm text-muted-foreground">
              No results — try a different phrase or broaden the filter.
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {filtered.map((result) => (
                <SearchResultRow key={result.id} result={result} />
              ))}
            </div>
          )}
        </>
      )}

      {!query && !loading && (
        <p className="text-sm text-muted-foreground">Enter a search to retrieve across the whole library.</p>
      )}
    </div>
  )
}
