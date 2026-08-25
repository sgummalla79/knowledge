import type { IngestionJob } from '../api/types'
import { formatBytes } from '../lib/formatBytes'
import { formatDuration } from '../lib/formatDuration'
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

// Relative time first (existing), then size and how long it took once finished, then any error
// last -- each only included when actually available, same "just omit it" convention the existing
// error_message handling already used.
function jobMeta(job: IngestionJob): string {
  const parts = [formatRelativeTime(job.created_at)]
  if (job.size_bytes !== null) parts.push(formatBytes(job.size_bytes))
  if (job.finished_at) parts.push(`took ${formatDuration(job.created_at, job.finished_at)}`)
  if (job.error_message) parts.push(job.error_message)
  return parts.join(' · ')
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
            <div className="truncate text-[11px] text-muted-foreground">{jobMeta(job)}</div>
          </div>
          <StatusBadge status={job.status} />
        </div>
      ))}
    </div>
  )
}
