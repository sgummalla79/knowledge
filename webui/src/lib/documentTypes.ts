import type { DocumentType } from '../api/types'

// The document_type Postgres enum (migration 0001) — a fixed schema value, not app config, so
// listing it here (rather than fetching it from an endpoint) matches how any other enum-backed
// UI constant in this codebase is handled. Shared by DocumentCard's type tag and Browse's filter.
export const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
  { value: 'article', label: 'Article' },
  { value: 'dataset', label: 'Dataset' },
  { value: 'guide', label: 'Guide' },
  { value: 'report', label: 'Report' },
  { value: 'faq', label: 'FAQ' },
  { value: 'media', label: 'Media' },
]

export function documentTypeLabel(type: string): string {
  return DOCUMENT_TYPES.find((entry) => entry.value === type)?.label ?? type
}
