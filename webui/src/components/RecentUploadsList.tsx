import type { IngestionJob } from '../api/types'
import { formatRelativeTime } from '../lib/formatRelativeTime'
import { StatusBadge } from './StatusBadge'

const TYPE_LABELS: Record<string, string> = {
  upload: 'Upload',
  crawl: 'Web crawl',
  reindex: 'Retry',
  resync: 'Resync',
}

// An upload job's real filename is far more useful than the generic "Upload" type label; crawl/
// reindex/resync jobs have no filename, so they keep falling back to their type label.
function jobLabel(job: IngestionJob): string {
  return job.payload_filename ?? TYPE_LABELS[job.type] ?? job.type
}

export function RecentUploadsList({ jobs }: { jobs: IngestionJob[] }) {
  if (jobs.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing uploaded yet.</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {jobs.map((job) => (
        <div key={job.id} className="flex items-center justify-between gap-4 rounded-sm bg-card px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm text-foreground">{jobLabel(job)}</div>
            <div className="truncate text-[11px] text-muted-foreground">
              {formatRelativeTime(job.created_at)}
              {job.error_message ? ` · ${job.error_message}` : ''}
            </div>
          </div>
          <StatusBadge status={job.status} />
        </div>
      ))}
    </div>
  )
}
