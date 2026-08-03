import { useEffect, useState } from 'react'
import { Modal } from './Modal'
import { useEmbeddingOptions, useEmbeddingProviderStatus, useUpdateEmbeddingProvider } from '../api/queries'

interface Props {
  providerName: string
  displayName: string
  onClose: () => void
}

export function ProviderSettingsModal({ providerName, displayName, onClose }: Props) {
  const { data: options } = useEmbeddingOptions()
  const { data: status, isLoading } = useEmbeddingProviderStatus(providerName)
  const option = options?.providers.find((candidate) => candidate.name === providerName)

  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [dimensions, setDimensions] = useState('')
  const [chunkSize, setChunkSize] = useState('')
  const [chunkOverlap, setChunkOverlap] = useState('')
  const [initialized, setInitialized] = useState(false)

  // Sync form fields from the fetched status exactly once — after that, re-fetches triggered by
  // our own mutations (invalidateQueries) must not clobber whatever the user is mid-typing.
  useEffect(() => {
    if (status && !initialized) {
      setModel(status.model ?? '')
      setBaseUrl(status.base_url ?? '')
      setDimensions(status.dimensions?.toString() ?? '')
      setChunkSize(status.chunk_size.toString())
      setChunkOverlap(status.chunk_overlap.toString())
      setInitialized(true)
    }
  }, [status, initialized])

  const update = useUpdateEmbeddingProvider(providerName)
  const error = update.error?.message

  const lockedByOther = status?.locked_by_other ?? false
  const locked = status?.locked ?? false

  function handleSave(event: React.FormEvent) {
    event.preventDefault()
    update.mutate({
      model: model.trim(),
      ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
      ...(option?.base_url_supported ? { base_url: baseUrl.trim() || null } : {}),
      dimensions: Number(dimensions),
      chunk_size: Number(chunkSize),
      chunk_overlap: Number(chunkOverlap),
    })
  }

  return (
    <Modal title={`${displayName} Embeddings`} onClose={onClose} wide>
      {isLoading && <p className="subtitle">Loading…</p>}
      {error && <div className="error-banner">{error}</div>}

      {status && (
        <form onSubmit={handleSave}>
          {lockedByOther && (
            <p className="subtitle">
              Another provider is currently active — only one provider can be active at a time, so {displayName}{' '}
              can't be configured until it's disabled first.
            </p>
          )}

          <label htmlFor="provider-api-key">API Key{!option?.api_key_required && ' (optional)'}</label>
          <input
            id="provider-api-key"
            type="password"
            autoComplete="off"
            placeholder={status.configured ? 'Leave blank to keep the current key' : 'Enter API key'}
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            disabled={lockedByOther}
          />

          {option?.base_url_supported && (
            <>
              <label htmlFor="provider-base-url">Base URL{!option.base_url_required && ' (optional)'}</label>
              <input
                id="provider-base-url"
                type="text"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                disabled={lockedByOther}
              />
            </>
          )}

          <div className="field-row">
            <div>
              <label htmlFor="provider-model">Model</label>
              <input
                id="provider-model"
                type="text"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                disabled={lockedByOther}
                readOnly={locked}
                required
              />
            </div>
            <div>
              <label htmlFor="provider-dimensions">Dimensions</label>
              <input
                id="provider-dimensions"
                type="number"
                min={1}
                value={dimensions}
                onChange={(event) => setDimensions(event.target.value)}
                disabled={lockedByOther}
                readOnly={locked}
                required
              />
            </div>
          </div>

          <div className="field-row">
            <div>
              <label htmlFor="provider-chunk-size">Chunk Size</label>
              <input
                id="provider-chunk-size"
                type="number"
                min={1}
                value={chunkSize}
                onChange={(event) => setChunkSize(event.target.value)}
                disabled={lockedByOther}
                required
              />
            </div>
            <div>
              <label htmlFor="provider-chunk-overlap">Chunk Overlap</label>
              <input
                id="provider-chunk-overlap"
                type="number"
                min={0}
                value={chunkOverlap}
                onChange={(event) => setChunkOverlap(event.target.value)}
                disabled={lockedByOther}
                required
              />
            </div>
          </div>

          {locked && (
            <p className="subtitle">
              Model and dimensions are locked, and this provider can't be disabled — {status.chunk_count} chunk
              {status.chunk_count === 1 ? '' : 's'} exist across every library. Delete every document first to
              change them. Chunk size, chunk overlap, and the API key can still be changed.
            </p>
          )}

          <div className="modal-actions">
            <button type="submit" disabled={lockedByOther || update.isPending}>
              Save
            </button>
            <button type="button" className="secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
