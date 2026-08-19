import { useEffect, useRef, useState } from 'react'

interface Props {
  definition: string
}

// mermaid.render() (returns an SVG string, inserted via dangerouslySetInnerHTML) rather than
// mermaid.run() (mutates DOM nodes in-place, fighting React's reconciliation) — same rationale
// applies to any future mermaid usage in this SPA.
export function ErDiagram({ definition }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    let cancelled = false
    import('mermaid').then(async (mod) => {
      const mermaid = mod.default
      mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' })
      try {
        const { svg: rendered } = await mermaid.render('data-model-er-diagram', definition)
        if (!cancelled) setSvg(rendered)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not render diagram.')
      }
    })
    return () => {
      cancelled = true
    }
  }, [definition])

  if (error) return <p className="text-sm text-destructive">{error}</p>
  if (!svg) return <p className="text-sm text-muted-foreground">Loading diagram…</p>

  return (
    <div>
      <div className="mb-3 flex gap-2">
        <button
          type="button"
          onClick={() => setScale((current) => Math.min(2, current + 0.15))}
          className="rounded-sm bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-accent hover:text-accent-foreground"
        >
          Zoom in
        </button>
        <button
          type="button"
          onClick={() => setScale((current) => Math.max(0.4, current - 0.15))}
          className="rounded-sm bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-accent hover:text-accent-foreground"
        >
          Zoom out
        </button>
        <button
          type="button"
          onClick={() => setScale(1)}
          className="rounded-sm bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-accent hover:text-accent-foreground"
        >
          Reset
        </button>
      </div>
      <div ref={containerRef} className="overflow-auto rounded-sm bg-card p-6" style={{ maxHeight: '70vh' }}>
        <div
          style={{ transform: `scale(${scale})`, transformOrigin: 'top left', width: 'fit-content' }}
          // Mermaid's own output — not user-supplied content, safe to inject.
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  )
}
