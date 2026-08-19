import { useParams } from 'react-router-dom'
import { useCategories, useDocument, useDocumentChunks, useDocumentShelves } from '../api/queries'
import { Breadcrumb } from '../components/Breadcrumb'
import { ChunksTable } from '../components/ChunksTable'
import { DocumentHeader } from '../components/DocumentHeader'
import { RelatedItems } from '../components/RelatedItems'
import { RetrievalStatsSidebar } from '../components/RetrievalStatsSidebar'

export function ItemPage() {
  const { id } = useParams<{ id: string }>()
  const document = useDocument(id)
  const chunks = useDocumentChunks(id)
  const shelves = useDocumentShelves(id)
  const categories = useCategories()

  if (document.isLoading) {
    return <p className="py-12 text-sm text-muted-foreground">Loading…</p>
  }

  if (document.isError || !document.data) {
    return (
      <div className="py-12">
        <Breadcrumb items={[{ label: 'Library', to: '/browse' }, { label: 'Not found' }]} />
        <p className="text-sm text-muted-foreground">This document doesn&apos;t exist or you don&apos;t have access to it.</p>
      </div>
    )
  }

  const doc = document.data
  const category = categories.data?.find((entry) => entry.id === doc.category_id) ?? null

  return (
    <div className="py-12">
      <Breadcrumb
        items={[
          { label: 'Library', to: '/browse' },
          ...(category ? [{ label: category.name, to: `/category/${category.slug}` }] : []),
          { label: doc.title },
        ]}
      />

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_300px]">
        <div>
          <DocumentHeader document={doc} category={category} shelves={shelves.data ?? []} />

          {doc.description && (
            <section className="mt-8">
              <h2 className="mb-2 text-lg font-semibold text-foreground">Overview</h2>
              <p className="text-sm text-muted-foreground">{doc.description}</p>
            </section>
          )}

          <section className="mt-8">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Chunks</h2>
            {chunks.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading chunks…</p>
            ) : (
              <ChunksTable chunks={chunks.data ?? []} />
            )}
          </section>
        </div>

        <div className="flex flex-col gap-6">
          <RetrievalStatsSidebar document={doc} />
          <RelatedItems categoryId={doc.category_id} excludeDocumentId={doc.id} />
        </div>
      </div>
    </div>
  )
}
