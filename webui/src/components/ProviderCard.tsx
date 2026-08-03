import { ToggleSwitch } from './ToggleSwitch'
import { LayersIcon } from './icons'
import { useDisableEmbeddingProvider, useEnableEmbeddingProvider } from '../api/queries'
import type { EmbeddingProviderOption } from '../api/types'

export function ProviderCard({ provider, onOpen }: { provider: EmbeddingProviderOption; onOpen: () => void }) {
  const enable = useEnableEmbeddingProvider(provider.name)
  const disable = useDisableEmbeddingProvider(provider.name)
  const error = enable.error?.message ?? disable.error?.message

  function handleToggle(event: React.MouseEvent) {
    event.stopPropagation()
    if (provider.enabled) disable.mutate()
    else enable.mutate()
  }

  return (
    <div className="provider-card" onClick={onOpen}>
      <div className="provider-card-top">
        <div className="provider-card-icon">
          <LayersIcon />
        </div>
        <h3>{provider.display_name}</h3>
        <ToggleSwitch
          checked={provider.enabled}
          disabled={enable.isPending || disable.isPending || (provider.enabled && provider.locked)}
          label={provider.enabled ? `Disable ${provider.display_name}` : `Enable ${provider.display_name}`}
          onClick={handleToggle}
        />
      </div>
      {error && <p className="provider-card-error">{error}</p>}
    </div>
  )
}
