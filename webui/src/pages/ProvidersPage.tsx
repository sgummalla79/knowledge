import { useState } from 'react'
import { ProviderSettingsModal } from '../components/ProviderSettingsModal'
import { ProviderCard } from '../components/ProviderCard'
import { LayersIcon } from '../components/icons'
import { useEmbeddingOptions } from '../api/queries'

export function ProvidersPage() {
  const { data, isLoading } = useEmbeddingOptions()
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const editingProviderOption = data?.providers.find((provider) => provider.name === editingProvider)

  return (
    <>
      <div className="settings-narrow">
        <div className="page-header">
          <div className="page-header-left">
            <div className="page-header-icon">
              <LayersIcon />
            </div>
            <div>
              <h1>Providers</h1>
              <p className="subtitle">Connect your embedding providers. Click a tile to manage credentials and models.</p>
            </div>
          </div>
        </div>

        {isLoading && <p className="subtitle">Loading…</p>}

        <div className="provider-grid">
          {(data?.providers ?? []).map((provider) => (
            <ProviderCard key={provider.name} provider={provider} onOpen={() => setEditingProvider(provider.name)} />
          ))}
        </div>
      </div>

      {editingProviderOption && (
        <ProviderSettingsModal
          providerName={editingProviderOption.name}
          displayName={editingProviderOption.display_name}
          onClose={() => setEditingProvider(null)}
        />
      )}
    </>
  )
}
