import { useState } from 'react'
import { SettingsSidebar } from '../components/SettingsSidebar'
import { ProviderSettingsModal } from '../components/ProviderSettingsModal'
import { ProviderCard } from '../components/ProviderCard'
import { useEmbeddingOptions } from '../api/queries'

export function SettingsPage() {
  const { data, isLoading } = useEmbeddingOptions()
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const editingProviderOption = data?.providers.find((provider) => provider.name === editingProvider)

  return (
    <div className="shell">
      <SettingsSidebar />
      <div className="main">
        <h1>Providers</h1>
        <p className="subtitle">Connect your embedding providers. Click a tile to manage credentials and models.</p>

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
    </div>
  )
}
