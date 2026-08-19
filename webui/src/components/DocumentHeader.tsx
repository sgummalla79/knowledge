import type { Category, Document, Shelf } from '../api/types'
import { documentTypeLabel } from '../lib/documentTypes'
import { formatRelativeTime } from '../lib/formatRelativeTime'

interface Props {
  document: Document
  category: Category | null
  shelves: Shelf[]
}

const tagClass = 'rounded-sm bg-accent px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent-foreground'

export function DocumentHeader({ document, category, shelves }: Props) {
  return (
    <header>
      <h1 className="mb-3 text-[30px] font-semibold leading-snug text-foreground">{document.title}</h1>
      <div className="mb-3 flex flex-wrap gap-2">
        <span className={tagClass}>{documentTypeLabel(document.type)}</span>
        {category && <span className={tagClass}>{category.name}</span>}
        {shelves.map((shelf) => (
          <span key={shelf.id} className={tagClass}>
            Shelf: {shelf.name}
          </span>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        <span>Updated {formatRelativeTime(document.indexed_at ?? document.created_at)}</span>
        {document.file_type && <span>Format: {document.file_type}</span>}
      </div>
    </header>
  )
}
