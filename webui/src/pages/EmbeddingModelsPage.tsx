import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useEmbeddingOptions, useEmbeddingSettings } from '../api/queries'
import type { EmbeddingOptionProvider, EmbeddingProviderConfig } from '../api/types'
import { Modal } from '../components/Modal'
import { Select } from '../components/Select'
import { useToast } from '../components/toastContext'

function statusLabel(config: EmbeddingProviderConfig): string {
  if (config.enabled) return 'Active'
  if (config.configured) return config.locked ? 'Retired — has chunks' : 'Configured'
  return 'Not configured'
}

function statusClass(config: EmbeddingProviderConfig): string {
  if (config.enabled) return 'bg-accent text-accent-foreground'
  if (config.configured) return 'bg-secondary text-foreground/70'
  return 'bg-secondary text-muted-foreground'
}

// The grid's raw `provider` key ("openai_compatible", ...) isn't a display string — display_name
// (api/constants.py's EMBEDDING_PROVIDER_DISPLAY_NAMES, served fresh by GET /embedding-options)
// already backs the provider Select's option labels below, so reuse that instead of a second
// lookup — the DB's embedding_models.name column carries the same value but is a write-once copy
// frozen at row-creation time, so it can't be relied on to reflect a label change later.
function providerDisplayName(provider: string, providers: EmbeddingOptionProvider[]): string {
  return providers.find((entry) => entry.name === provider)?.display_name ?? provider
}

interface ProviderConfigFormProps {
  provider: string
  providers: EmbeddingOptionProvider[]
  config: EmbeddingProviderConfig | undefined
  option: EmbeddingOptionProvider | undefined
  onProviderChange: (provider: string) => void
  onSaved: () => void
  onClose: () => void
}

// Keyed by `provider` in the parent so switching providers remounts this component with fresh
// initial state (from `config`/`option`) rather than needing a reset-on-prop-change effect.
function ProviderConfigForm({ provider, providers, config, option, onProviderChange, onSaved, onClose }: ProviderConfigFormProps) {
  const { showToast } = useToast()
  const [model, setModel] = useState(config?.model ?? '')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState(config?.base_url ?? option?.default_base_url ?? '')
  const [dimensions, setDimensions] = useState(config?.dimensions ? String(config.dimensions) : '')
  const [makeActive, setMakeActive] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [liveModels, setLiveModels] = useState<string[]>([])
  const [listingModels, setListingModels] = useState(false)

  async function handleListModels() {
    setListingModels(true)
    try {
      const { models } = await api.post<{ models: string[] }>('/embedding-options/models', {
        provider,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
      })
      setLiveModels(models)
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Could not list models for this provider.', 'error')
    } finally {
      setListingModels(false)
    }
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.put(`/embedding-settings/${provider}`, {
        model,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        dimensions: Number(dimensions),
      })
      if (makeActive) {
        await api.post(`/embedding-settings/${provider}/enable`)
      }
      onSaved()
      showToast('Embedding provider saved.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-4">
      {error && (
        <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div>
        <label htmlFor="provider" className="mb-1.5 block text-sm text-foreground">
          Provider
        </label>
        <Select
          id="provider"
          value={provider}
          onChange={onProviderChange}
          options={providers.map((entry) => ({ value: entry.name, label: entry.display_name }))}
          className="w-full px-4 py-2.5 text-[15px]"
        />
        {config?.locked_by_other && (
          <p className="mt-1 text-xs text-muted-foreground">
            Another provider is active — disable it before configuring this one.
          </p>
        )}
      </div>

      <div>
        <label htmlFor="model" className="mb-1.5 block text-sm text-foreground">
          Model identifier
        </label>
        <input
          id="model"
          placeholder="e.g. nomic-embed-text"
          value={model}
          onChange={(event) => setModel(event.target.value)}
          className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
        />
        {option?.supports_model_listing && (
          <button
            type="button"
            onClick={() => void handleListModels()}
            disabled={listingModels}
            className="mt-1.5 text-xs text-primary hover:underline disabled:opacity-60"
          >
            {listingModels ? 'Listing models…' : 'List available models with these credentials'}
          </button>
        )}
        {liveModels.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {liveModels.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setModel(name)}
                className="rounded-sm bg-secondary px-2 py-1 text-xs text-foreground hover:bg-accent hover:text-accent-foreground"
              >
                {name}
              </button>
            ))}
          </div>
        )}
      </div>

      {option?.api_key_required && (
        <div>
          <label htmlFor="api-key" className="mb-1.5 block text-sm text-foreground">
            API key
          </label>
          <input
            id="api-key"
            type="password"
            placeholder="Stored, never shown again after saving"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
          />
        </div>
      )}

      {option?.base_url_supported && (
        <div>
          <label htmlFor="base-url" className="mb-1.5 block text-sm text-foreground">
            Endpoint URL{option.base_url_required ? '' : ' (optional)'}
          </label>
          <input
            id="base-url"
            placeholder={option.default_base_url ?? 'https://embed.example.internal/v1'}
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
          />
        </div>
      )}

      <div>
        <label htmlFor="dimensions" className="mb-1.5 block text-sm text-foreground">
          Dimensions
        </label>
        <input
          id="dimensions"
          type="number"
          placeholder="e.g. 768"
          value={dimensions}
          onChange={(event) => setDimensions(event.target.value)}
          className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={makeActive}
          onChange={(event) => setMakeActive(event.target.checked)}
          className="accent-primary"
        />
        Make this the org&apos;s active model — disables the current active provider
      </label>

      <div className="mt-2 flex justify-end gap-3">
        <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
          Close
        </button>
        <button
          type="submit"
          disabled={saving}
          className="rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {saving ? 'Saving…' : 'Save provider'}
        </button>
      </div>
    </form>
  )
}

export function EmbeddingModelsPage() {
  const { showToast } = useToast()
  const queryClient = useQueryClient()
  const settings = useEmbeddingSettings()
  const options = useEmbeddingOptions()
  const [manuallySelected, setManuallySelected] = useState<string | null>(null)
  const [configuring, setConfiguring] = useState(false)

  const providers = options.data?.providers ?? []
  const configs = settings.data ?? []
  const selectedProvider = manuallySelected ?? providers[0]?.name ?? null
  const selectedConfig = configs.find((config) => config.provider === selectedProvider)
  const selectedOption = providers.find((provider) => provider.name === selectedProvider)

  async function refetch() {
    await queryClient.invalidateQueries({ queryKey: ['embedding-settings'] })
    await queryClient.invalidateQueries({ queryKey: ['embedding-options'] })
  }

  async function handleToggleActive(provider: string, enable: boolean) {
    try {
      await api.post(`/embedding-settings/${provider}/${enable ? 'enable' : 'disable'}`)
      await refetch()
      showToast(enable ? 'Provider enabled.' : 'Provider disabled.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <h1 className="text-[26px] font-semibold text-foreground">Embedding model</h1>
        <button
          type="button"
          onClick={() => setConfiguring(true)}
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          Add provider
        </button>
      </div>
      <p className="mb-8 max-w-xl text-sm text-muted-foreground">
        Exactly one provider is active at a time — the org embeds with a single model, not a
        per-category choice. Switching providers is blocked while documents exist, since
        embeddings from different models aren&apos;t comparable.
      </p>

      <div className="mb-10 overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
              <th className="pb-2.5 font-semibold">Provider</th>
              <th className="pb-2.5 font-semibold">Model</th>
              <th className="pb-2.5 font-semibold">Dimensions</th>
              <th className="pb-2.5 font-semibold">Status</th>
              <th className="pb-2.5 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.provider} className="border-t border-border">
                <td className="py-3 pr-4 font-medium text-foreground">{providerDisplayName(config.provider, providers)}</td>
                <td className="py-3 pr-4 text-foreground">{config.model ?? '—'}</td>
                <td className="py-3 pr-4 text-muted-foreground">{config.dimensions ?? '—'}</td>
                <td className="py-3 pr-4">
                  <span
                    className={`rounded-sm px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${statusClass(config)}`}
                  >
                    {statusLabel(config)}
                  </span>
                </td>
                <td className="py-3 text-right">
                  {config.configured && !config.locked_by_other && (
                    <button
                      type="button"
                      onClick={() => void handleToggleActive(config.provider, !config.enabled)}
                      disabled={config.locked}
                      className="text-[13px] text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted-foreground disabled:no-underline"
                      title={config.locked ? "Can't disable — chunks reference this provider" : undefined}
                    >
                      {config.enabled ? 'Disable' : 'Enable'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {configuring && selectedProvider && (
        <Modal title="Configure a provider" onClose={() => setConfiguring(false)} maxWidthClassName="max-w-lg">
          <ProviderConfigForm
            key={selectedProvider}
            provider={selectedProvider}
            providers={providers}
            config={selectedConfig}
            option={selectedOption}
            onProviderChange={setManuallySelected}
            onSaved={() => {
              void refetch()
              setConfiguring(false)
            }}
            onClose={() => setConfiguring(false)}
          />
        </Modal>
      )}
    </div>
  )
}
