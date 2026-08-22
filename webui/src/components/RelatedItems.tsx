import { Link } from 'react-router-dom'
import { useDocuments } from '../api/queries'

interface Props {
  categoryId: string | null
  excludeDocumentId: string
}

// The mockup's "Related items" implies a similarity model this app doesn't have (no
// document-to-document relatedness is computed anywhere) — labeled honestly as same-category
// documents instead of fabricating a relatedness score.
export function RelatedItems({ categoryId, excludeDocumentId }: Props) {
  const documents = useDocuments({ categoryId: categoryId ?? undefined, limit: 4 }, { enabled: categoryId !== null })

  if (!categoryId) return null
  const related = (documents.data?.items ?? []).filter((document) => document.id !== excludeDocumentId).slice(0, 3)
  if (related.length === 0) return null

  return (
    <aside className="rounded-sm bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold text-foreground">More in this category</h3>
      <div className="flex flex-col gap-2.5">
        {related.map((document) => (
          <Link key={document.id} to={`/item/${document.id}`} className="text-sm text-foreground hover:text-primary">
            {document.title}
          </Link>
        ))}
      </div>
    </aside>
  )
}
