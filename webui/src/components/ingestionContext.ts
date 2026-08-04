import { createContext, useContext } from 'react'
import type { CrawlJobStatus } from '../api/types'

export type IngestionKind = 'upload' | 'crawl'

export interface IngestionContextValue {
  // True whenever ANY upload or crawl is running, in ANY library — a single global lock so
  // starting one kind of ingestion blocks the other too, everywhere, not just within whichever
  // library page happens to be mounted.
  isBusy: boolean
  activeKind: IngestionKind | null
  activeLibraryId: string | null

  // Upload-specific — only meaningful while activeKind === 'upload'.
  uploadElapsedSeconds: number
  uploadJobStatusLabel: string | null
  startUpload: (libraryId: string, file: File) => void

  // Crawl-specific — only meaningful while activeKind === 'crawl'.
  crawlJobStatus: CrawlJobStatus | null
  startCrawl: (libraryId: string, input: { url: string; maxPages: number; scopePrefix: string | null }) => void
}

export const IngestionContext = createContext<IngestionContextValue | null>(null)

export function useIngestion(): IngestionContextValue {
  const context = useContext(IngestionContext)
  if (!context) throw new Error('useIngestion must be used within an IngestionProvider')
  return context
}
