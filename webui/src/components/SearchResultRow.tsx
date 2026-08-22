import { Link } from 'react-router-dom'
import type { RoutedChunk } from '../api/types'
import { documentTypeLabel } from '../lib/documentTypes'

export function SearchResultRow({ result }: { result: RoutedChunk }) {
  return (
    <Link to={`/item/${result.document_id}`} className="block rounded-sm bg-card p-5 hover:shadow-md">
      <div className="mb-1.5 flex items-center gap-2 text-[10px] uppercase tracking-wide text-primary">
        <span>{documentTypeLabel(result.document_type)}</span>
        <span className="text-muted-foreground">· {result.category_name}</span>
      </div>
      <div className="mb-1 font-semibold text-foreground">{result.document_title}</div>
      <p className="line-clamp-2 text-[13px] text-muted-foreground">{result.content}</p>
    </Link>
  )
}
