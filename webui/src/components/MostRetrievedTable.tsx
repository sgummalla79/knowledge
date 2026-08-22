import { Link } from 'react-router-dom'
import type { MostRetrievedDocument } from '../api/types'

export function MostRetrievedTable({ documents }: { documents: MostRetrievedDocument[] }) {
  if (documents.length === 0) {
    return <p className="text-sm text-muted-foreground">No retrieval activity yet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="pb-2.5 font-semibold">Title</th>
            <th className="pb-2.5 font-semibold">Retrievals (30d)</th>
            <th className="pb-2.5 font-semibold">Avg relevance score</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.document_id} className="border-t border-border">
              <td className="py-3 pr-4">
                <Link to={`/item/${document.document_id}`} className="text-foreground hover:text-primary">
                  {document.title}
                </Link>
              </td>
              <td className="py-3 pr-4 text-foreground">{document.retrieval_count}</td>
              {/* A fused (RRF) score, not a 0-1 cosine similarity — see rrf.py — so this is a raw
                  relative-ranking number, never rendered as a "%". */}
              <td className="py-3 text-muted-foreground">{document.avg_similarity.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
