import { useEmbeddingSettings } from '../api/queries'
import type { Document } from '../api/types'
import { formatRelativeTime } from '../lib/formatRelativeTime'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-t border-border py-2.5 text-sm first:border-t-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  )
}

export function RetrievalStatsSidebar({ document }: { document: Document }) {
  const embeddingSettings = useEmbeddingSettings()
  const activeProvider = embeddingSettings.data?.find((config) => config.provider === config.active_provider)

  return (
    <aside className="rounded-sm bg-card p-5">
      <h3 className="mb-1 text-sm font-semibold text-foreground">Retrieval</h3>
      <Row label="Times retrieved" value={String(document.retrieval_count ?? 0)} />
      {/* A fused (RRF) relevance score, not a 0-1 cosine similarity — see rrf.py — shown as a raw
          number, never as a "%". */}
      <Row
        label="Avg relevance score"
        value={document.avg_similarity != null ? document.avg_similarity.toFixed(4) : '—'}
      />
      <Row label="Embedding model" value={activeProvider?.model ?? 'Not configured'} />
      <Row label="Chunks" value={String(document.chunk_count ?? 0)} />
      <Row
        label="Last indexed"
        value={document.indexed_at ? formatRelativeTime(document.indexed_at) : 'Not indexed yet'}
      />
    </aside>
  )
}
