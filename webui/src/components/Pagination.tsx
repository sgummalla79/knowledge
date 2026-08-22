interface Props {
  offset: number
  limit: number
  total: number
  onOffsetChange: (offset: number) => void
}

export function Pagination({ offset, limit, total, onOffsetChange }: Props) {
  const currentPage = Math.floor(offset / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit))
  if (totalPages <= 1) return null

  return (
    <div className="mt-10 flex items-center justify-center gap-5 text-sm">
      <button
        type="button"
        disabled={currentPage === 1}
        onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
      >
        Prev
      </button>
      <span className="text-muted-foreground">
        Page {currentPage} of {totalPages}
      </span>
      <button
        type="button"
        disabled={currentPage >= totalPages}
        onClick={() => onOffsetChange(offset + limit)}
        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
      >
        Next
      </button>
    </div>
  )
}
