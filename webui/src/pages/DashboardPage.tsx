import { useDashboardStats, useIngestionJobs } from '../api/queries'
import { IngestionActivityTable } from '../components/IngestionActivityTable'
import { MostRetrievedTable } from '../components/MostRetrievedTable'
import { StatTile } from '../components/StatTile'

export function DashboardPage() {
  const stats = useDashboardStats()
  const jobs = useIngestionJobs(10)

  return (
    <div className="py-12">
      <h1 className="mb-1 text-[32px] font-semibold text-foreground">Library dashboard</h1>
      <p className="mb-10 text-sm text-muted-foreground">Ingestion and retrieval activity across the library.</p>

      <div className="mb-14 grid grid-cols-2 gap-8 sm:grid-cols-4">
        <StatTile label="Documents indexed" value={stats.data?.document_count ?? null} loading={stats.isLoading} />
        <StatTile label="Chunks embedded" value={stats.data?.chunk_count ?? null} loading={stats.isLoading} />
        <StatTile label="Queries served (30d)" value={stats.data?.queries_last_30d ?? null} loading={stats.isLoading} />
        <StatTile
          label="Avg retrieval latency"
          value={stats.data?.avg_query_latency_ms != null ? `${Math.round(stats.data.avg_query_latency_ms)}ms` : '—'}
          loading={stats.isLoading}
        />
      </div>

      <section className="mb-14">
        <h2 className="mb-4 text-lg font-semibold text-foreground">Most retrieved documents</h2>
        {stats.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <MostRetrievedTable documents={stats.data?.most_retrieved_documents ?? []} />
        )}
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">Ingestion activity</h2>
        {jobs.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <IngestionActivityTable jobs={jobs.data ?? []} />
        )}
      </section>
    </div>
  )
}
