import { useEffect, useRef, useState } from 'react'
import { MoreIcon, PencilIcon, TrashIcon } from './icons'

interface Props {
  onRename: () => void
  onDelete: () => void
}

export function LibraryItemMenu({ onRename, onDelete }: Props) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  // The item itself is a <Link> — every button here needs to stop the click from bubbling up to
  // it (and preventDefault, since a <button> inside an <a> would otherwise still trigger the
  // navigation via the native click) or opening this menu / choosing an action would also
  // navigate to the library.
  function stop(event: React.MouseEvent) {
    event.preventDefault()
    event.stopPropagation()
  }

  return (
    <div className={`rail-item-menu ${open ? 'is-open' : ''}`} ref={containerRef}>
      <button
        type="button"
        className="icon-btn"
        aria-label="Library actions"
        onClick={(event) => {
          stop(event)
          setOpen((current) => !current)
        }}
      >
        <MoreIcon />
      </button>
      {open && (
        <div className="rail-item-menu-popover">
          <button
            type="button"
            className="rail-item-menu-item"
            onClick={(event) => {
              stop(event)
              setOpen(false)
              onRename()
            }}
          >
            <PencilIcon />
            Rename
          </button>
          <button
            type="button"
            className="rail-item-menu-item rail-item-menu-item-destructive"
            onClick={(event) => {
              stop(event)
              setOpen(false)
              onDelete()
            }}
          >
            <TrashIcon />
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
