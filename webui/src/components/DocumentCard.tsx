import { Link } from 'react-router-dom'
import type { Document } from '../api/types'
import { documentTypeLabel } from '../lib/documentTypes'
import { formatRelativeTime } from '../lib/formatRelativeTime'

export function DocumentCard({ document }: { document: Document }) {
  return (
    <Link
      to={`/item/${document.id}`}
      className="flex flex-col gap-2.5 rounded-sm bg-card p-5 transition-shadow hover:shadow-md"
    >
      <span className="w-fit rounded-sm bg-accent px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent-foreground">
        {documentTypeLabel(document.type)}
      </span>
      <span className="font-semibold leading-snug text-foreground">{document.title}</span>
      {document.description && (
        <p className="line-clamp-2 text-[13px] text-muted-foreground">{document.description}</p>
      )}
      <div className="mt-auto text-[11px] text-muted-foreground">
        Updated {formatRelativeTime(document.indexed_at ?? document.created_at)}
        {document.chunk_count != null ? ` · ${document.chunk_count} chunks` : ''}
      </div>
    </Link>
  )
}
