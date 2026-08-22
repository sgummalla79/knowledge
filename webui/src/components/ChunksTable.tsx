import type { Chunk } from '../api/types'

export function ChunksTable({ chunks }: { chunks: Chunk[] }) {
  if (chunks.length === 0) {
    return <p className="text-sm text-muted-foreground">No chunks yet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="pb-2.5 font-semibold">Chunk</th>
            <th className="pb-2.5 font-semibold">Preview</th>
            <th className="pb-2.5 font-semibold">Tokens</th>
            <th className="pb-2.5 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {chunks.map((chunk) => (
            <tr key={chunk.id} className="border-t border-border">
              <td className="py-3 pr-4 font-mono text-xs text-muted-foreground">#{String(chunk.ordinal).padStart(4, '0')}</td>
              <td className="max-w-md truncate py-3 pr-4 text-foreground">{chunk.content}</td>
              <td className="py-3 pr-4 text-foreground">{chunk.token_count}</td>
              <td className="py-3">
                {/* A chunk row only ever exists after successful embedding — every persisted
                    chunk is "Indexed" by construction, there's no other state to show here. */}
                <span className="rounded-sm bg-accent px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-accent-foreground">
                  Indexed
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
