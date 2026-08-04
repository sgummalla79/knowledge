import { ToggleSwitch } from './ToggleSwitch'
import { LayersIcon } from './icons'
import { useToast } from './toastContext'
import { useDisableEmbeddingProvider, useEnableEmbeddingProvider } from '../api/queries'
import type { EmbeddingProviderOption } from '../api/types'

export function ProviderCard({ provider, onOpen }: { provider: EmbeddingProviderOption; onOpen: () => void }) {
  const { showToast } = useToast()
  const enable = useEnableEmbeddingProvider(provider.name)
  const disable = useDisableEmbeddingProvider(provider.name)

  function handleToggle(event: React.MouseEvent) {
    event.stopPropagation()
    const mutation = provider.enabled ? disable : enable
    mutation.mutate(undefined, { onError: (error) => showToast(error.message) })
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
    </div>
  )
}
