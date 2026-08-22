import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useDashboardStats, useDocuments } from '../api/queries'
import type { Document } from '../api/types'
import { DocumentCard } from '../components/DocumentCard'
import { SearchIcon } from '../components/icons'
import { StatTile } from '../components/StatTile'
import { DOCUMENT_TYPES } from '../lib/documentTypes'

export function HomePage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const stats = useDashboardStats()
  const recent = useDocuments({ sort: '-created_at', limit: 3 })

  const typeCounts = useQueries({
    queries: DOCUMENT_TYPES.map((type) => ({
      queryKey: ['documents', 'type-count', type.value],
      queryFn: () => api.getPaginated<Document>(`/documents?type=${type.value}&limit=1`),
    })),
  })

  function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}`)
  }

  return (
    <div className="py-16">
      <div className="mb-3 text-[11px] font-medium uppercase tracking-widest text-primary">Knowledge library</div>
      <h1 className="mb-5 whitespace-nowrap text-[44px] font-semibold leading-tight text-foreground">
        Every source your assistant can cite.
      </h1>
      <p className="mb-8 max-w-lg text-base text-muted-foreground">
        Articles and documents — indexed, chunked and ready for retrieval. Search the library the
        way your RAG pipeline does.
      </p>

      <form onSubmit={handleSearch} className="mb-12 flex max-w-xl gap-2.5">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search articles, documents…"
          className="flex-1 rounded-sm border border-border bg-secondary px-4 py-3 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          className="flex items-center gap-2 rounded-sm bg-primary px-6 py-3 text-[15px] font-semibold text-primary-foreground hover:opacity-90"
        >
          <SearchIcon /> Search
        </button>
      </form>

      <div className="mb-16 flex gap-10">
        <StatTile label="documents indexed" value={stats.data?.document_count ?? null} loading={stats.isLoading} />
        <StatTile label="chunks embedded" value={stats.data?.chunk_count ?? null} loading={stats.isLoading} />
        <StatTile
          label="queries served (30d)"
          value={stats.data?.queries_last_30d ?? null}
          loading={stats.isLoading}
        />
      </div>

      <section className="mb-14">
        <h2 className="mb-5 text-2xl font-semibold text-foreground">Browse by type</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {DOCUMENT_TYPES.map((type, index) => (
            <Link
              key={type.value}
              to={`/browse?type=${type.value}`}
              className="rounded-sm bg-card p-5 transition-shadow hover:shadow-md"
            >
              <div className="mb-1.5 text-[10px] uppercase tracking-wide text-primary">
                {typeCounts[index]?.data?.total ?? '–'} items
              </div>
              <div className="text-lg font-semibold text-foreground">{type.label}</div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-5 flex items-baseline justify-between">
          <h2 className="text-2xl font-semibold text-foreground">Recently added</h2>
          <Link to="/browse" className="text-sm text-primary hover:underline">
            View all
          </Link>
        </div>
        {recent.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {recent.data && recent.data.items.length === 0 && (
          <p className="rounded-sm bg-card p-8 text-center text-sm text-muted-foreground">
            No documents yet — add your first one from Contribute.
          </p>
        )}
        {recent.data && recent.data.items.length > 0 && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            {recent.data.items.map((document) => (
              <DocumentCard key={document.id} document={document} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
