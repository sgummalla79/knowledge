import { useState } from 'react'
import { api } from '../api/client'
import type { Tag } from '../api/types'

interface Props {
  tags: Tag[]
  onAdd: (tag: Tag) => void | Promise<void>
  onRemove: (tagId: string) => void | Promise<void>
  placeholder?: string
}

// Gmail-style tag input: type a name, then Tab/click away or press Enter to commit it as a
// removable pill. POST /tags is a case-insensitive get-or-create (TagService.create_tag) —
// "Billing" reuses an existing "billing" — so this always just posts the typed name and uses
// whatever tag comes back, new or reused, rather than pre-matching against a locally known tag
// list itself (that dedup used to live here, case-sensitively; moved server-side so every caller,
// not just this component, gets the same non-duplicating behavior). Pills render inside the same
// bordered box as the text caret (one control, focus-within ring) rather than as a separate row
// floating above a second input box — that stacked-box version put a max-w-md cap on the input
// alone, so its right edge lined up with nothing else on the page; a single full-width control
// lines up with the dropdowns above it instead. Shared by DocumentOrganizePanel (tags on an
// already-indexed document, saved immediately via onAdd/onRemove hitting the API) and UploadPage
// (tags on a not-yet-created document, held in local state until the upload finishes).
export function TagPillInput({ tags, onAdd, onRemove, placeholder }: Props) {
  const [inputValue, setInputValue] = useState('')
  const [busy, setBusy] = useState(false)

  async function commit() {
    const names = inputValue.split(',').map((entry) => entry.trim()).filter(Boolean)
    if (names.length === 0) return
    setInputValue('')
    setBusy(true)
    try {
      for (const name of names) {
        const tag = await api.post<Tag>('/tags', { name })
        await onAdd(tag)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex w-full flex-wrap items-center gap-1.5 rounded-sm border border-border bg-secondary px-3 py-2 focus-within:ring-2 focus-within:ring-ring">
      {tags.map((tag) => (
        <span
          key={tag.id}
          className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-background px-2.5 py-1 text-xs text-foreground"
        >
          {tag.name}
          <button
            type="button"
            onClick={() => void onRemove(tag.id)}
            aria-label={`Remove tag ${tag.name}`}
            className="text-muted-foreground hover:text-foreground"
          >
            ✕
          </button>
        </span>
      ))}
      <input
        value={inputValue}
        disabled={busy}
        onChange={(event) => setInputValue(event.target.value)}
        onBlur={() => void commit()}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault()
            void commit()
          }
        }}
        placeholder={tags.length === 0 ? (placeholder ?? 'Type a tag, then press Tab or Enter') : 'Add another…'}
        className="min-w-[8rem] flex-1 bg-transparent px-1 py-1 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
      />
    </div>
  )
}
