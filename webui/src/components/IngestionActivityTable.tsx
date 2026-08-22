import type { IngestionJob } from '../api/types'
import { formatRelativeTime } from '../lib/formatRelativeTime'
import { StatusBadge } from './StatusBadge'

const TYPE_LABELS: Record<string, string> = {
  upload: 'Upload',
  crawl: 'Web crawl',
  reindex: 'Retry',
  resync: 'Resync',
}

export function IngestionActivityTable({ jobs }: { jobs: IngestionJob[] }) {
  if (jobs.length === 0) {
    return <p className="text-sm text-muted-foreground">No ingestion activity yet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="pb-2.5 font-semibold">Source</th>
            <th className="pb-2.5 font-semibold">Status</th>
            <th className="pb-2.5 font-semibold">Items</th>
            <th className="pb-2.5 font-semibold">Started</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-t border-border">
              <td className="py-3 pr-4 text-foreground">{TYPE_LABELS[job.type] ?? job.type}</td>
              <td className="py-3 pr-4">
                <StatusBadge status={job.status} />
              </td>
              <td className="py-3 pr-4 text-foreground">{job.items_processed}</td>
              <td className="py-3 text-muted-foreground">{formatRelativeTime(job.started_at ?? job.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
