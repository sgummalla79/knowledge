import { SettingsSidebar } from '../components/SettingsSidebar'
import { useEmbeddingOptions } from '../api/queries'
import { LayersIcon } from '../components/icons'

export function SettingsPage() {
  const { data, isLoading } = useEmbeddingOptions()

  return (
    <div className="shell">
      <SettingsSidebar />
      <div className="main">
        <h1>Providers</h1>
        <p className="subtitle">Connect your embedding providers. Click a tile to manage credentials and models.</p>

        {isLoading && <p className="subtitle">Loading…</p>}

        <div className="provider-grid">
          {(data?.providers ?? []).map((provider) => (
            <a key={provider.name} href={`/dashboard/configuration/embeddings/${provider.name}`} className="provider-card">
              <div className="provider-card-icon">
                <LayersIcon />
              </div>
              <div className="provider-card-body">
                <h3>{provider.display_name}</h3>
                <p>{provider.name}</p>
              </div>
              <span className={`badge ${provider.enabled ? 'status-completed' : 'status-failed'}`}>
                {provider.enabled ? 'Connected' : 'Not connected'}
              </span>
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
