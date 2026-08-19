import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Breadcrumb } from '../components/Breadcrumb'
import { DocumentCard } from '../components/DocumentCard'
import { Pagination } from '../components/Pagination'
import { useCategories, useDocuments } from '../api/queries'

const PAGE_SIZE = 12

export function CategoryPage() {
  const { slug } = useParams<{ slug: string }>()
  const [offset, setOffset] = useState(0)
  const categories = useCategories()
  const category = categories.data?.find((entry) => entry.slug === slug)

  const documents = useDocuments(
    { categoryId: category?.id, limit: PAGE_SIZE, offset },
    // Only fetch once the category has resolved — an id-less request would return every
    // document in the org, not this category's.
    { enabled: category !== undefined },
  )

  if (categories.isLoading) {
    return <p className="py-12 text-sm text-muted-foreground">Loading…</p>
  }

  if (!category) {
    return (
      <div className="py-12">
        <Breadcrumb items={[{ label: 'Library', to: '/browse' }, { label: 'Category not found' }]} />
        <p className="text-sm text-muted-foreground">No category matches this URL.</p>
      </div>
    )
  }

  return (
    <div className="py-12">
      <Breadcrumb items={[{ label: 'Library', to: '/browse' }, { label: category.name }]} />
      <h1 className="mb-2 text-[32px] font-semibold text-foreground">{category.name}</h1>
      {category.description && <p className="mb-2 max-w-xl text-sm text-muted-foreground">{category.description}</p>}
      <p className="mb-8 text-sm text-muted-foreground">
        {documents.data ? `${documents.data.total} items` : 'Loading…'}
      </p>

      {documents.isLoading && <p className="text-sm text-muted-foreground">Loading documents…</p>}
      {documents.data && documents.data.items.length === 0 && (
        <p className="rounded-sm bg-card p-8 text-center text-sm text-muted-foreground">
          No documents in this category yet.
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
  )
}
