import { useEffect, useState } from 'react'
import { GlobeIcon } from '../components/icons'
import { useToast } from '../components/toastContext'
import { useUpdateWebCrawlSettings, useWebCrawlSettings } from '../api/queries'

export function WebCrawlerPage() {
  const { showToast } = useToast()
  const { data, isLoading } = useWebCrawlSettings()
  const update = useUpdateWebCrawlSettings()

  const [userAgent, setUserAgent] = useState('')
  const [initialized, setInitialized] = useState(false)

  // Sync the field from the fetched settings exactly once — after that, the refetch triggered by
  // our own mutation (invalidateQueries) must not clobber whatever the user is mid-typing.
  useEffect(() => {
    if (data && !initialized) {
      setUserAgent(data.user_agent)
      setInitialized(true)
    }
  }, [data, initialized])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    update.mutate(userAgent.trim(), { onError: (error) => showToast(error.message) })
  }

  return (
    <div className="settings-narrow">
      <div className="page-header">
        <div className="page-header-left">
          <div className="page-header-icon">
            <GlobeIcon />
          </div>
          <div>
            <h1>Web Crawler</h1>
            <p className="subtitle">
              User-Agent sent when fetching pages for "Add from URL". Some sites block requests that
              identify themselves as automated tools — changing this to something less pattern-matched
              (e.g. mimicking a plain HTTP client) is a deliberate tradeoff: it can get past that
              blocking, but works around the target site's stated preference not to be scraped, and
              isn't guaranteed to work on every site.
            </p>
          </div>
        </div>
      </div>

      {isLoading && <p className="subtitle">Loading…</p>}

      {data && (
        <form onSubmit={handleSubmit}>
          <label htmlFor="web-crawler-user-agent">User-Agent</label>
          <input
            id="web-crawler-user-agent"
            type="text"
            value={userAgent}
            onChange={(event) => setUserAgent(event.target.value)}
            required
          />
          <div className="modal-actions">
            <button type="submit" disabled={update.isPending || userAgent.trim().length === 0}>
              Save
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
