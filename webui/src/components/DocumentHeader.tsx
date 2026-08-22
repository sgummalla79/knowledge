import type { Document } from '../api/types'
import { formatRelativeTime } from '../lib/formatRelativeTime'

interface Props {
  document: Document
}

// Type/category/shelves/tags used to render here as read-only pills — now editable, so they live
// in DocumentOrganizePanel instead (a static pill can't also be a control without either
// duplicating the UI or this component reaching into shelf/tag mutation state it has no other
// reason to know about).
export function DocumentHeader({ document }: Props) {
  return (
    <header>
      <h1 className="mb-3 text-[30px] font-semibold leading-snug text-foreground">{document.title}</h1>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        <span>Updated {formatRelativeTime(document.indexed_at ?? document.created_at)}</span>
        {document.file_type && <span>Format: {document.file_type}</span>}
      </div>
    </header>
  )
}
