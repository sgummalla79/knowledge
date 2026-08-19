import { Link } from 'react-router-dom'
import type { Category, Shelf } from '../api/types'
import { DOCUMENT_TYPES } from '../lib/documentTypes'

interface Props {
  categories: Category[]
  shelves: Shelf[]
  selectedType: string | null
  selectedShelfId: string | null
  onTypeChange: (type: string | null) => void
  onShelfChange: (shelfId: string | null) => void
}

function optionClass(active: boolean) {
  return `block w-full rounded-sm px-2.5 py-1.5 text-left text-[13px] ${
    active ? 'bg-accent text-accent-foreground' : 'text-foreground/80 hover:bg-secondary'
  }`
}

export function FilterSidebar({ categories, shelves, selectedType, selectedShelfId, onTypeChange, onShelfChange }: Props) {
  return (
    <aside className="w-56 shrink-0">
      <div className="mb-7">
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Content type
        </h3>
        <button type="button" onClick={() => onTypeChange(null)} className={optionClass(selectedType === null)}>
          All types
        </button>
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type.value}
            type="button"
            onClick={() => onTypeChange(type.value)}
            className={optionClass(selectedType === type.value)}
          >
            {type.label}
          </button>
        ))}
      </div>

      <div className="mb-7">
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Shelf</h3>
        <button type="button" onClick={() => onShelfChange(null)} className={optionClass(selectedShelfId === null)}>
          All accessible shelves
        </button>
        {shelves.map((shelf) => (
          <button
            key={shelf.id}
            type="button"
            onClick={() => onShelfChange(shelf.id)}
            className={optionClass(selectedShelfId === shelf.id)}
          >
            {shelf.name}
          </button>
        ))}
      </div>

      {categories.length > 0 && (
        <div>
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Category</h3>
          {categories.map((category) => (
            <Link key={category.id} to={`/category/${category.slug}`} className={optionClass(false)}>
              {category.name}
            </Link>
          ))}
        </div>
      )}
    </aside>
  )
}
