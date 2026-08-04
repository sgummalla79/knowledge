import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

const MIN_SCALE = 0.4
const MAX_SCALE = 2.5
const STEP = 0.15

// Static hex, not read from CSS custom properties at runtime: this app's tokens are oklch(...),
// and mermaid's own color library can't parse that format ("Unsupported color format"). These are
// the actual rendered-pixel equivalents of --background/--foreground/--primary/--secondary/
// --muted-foreground/--border, sampled once directly from a screenshot rather than resolved live.
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    background: '#020817',
    primaryColor: '#1e293b',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#1e293b',
    lineColor: '#1e293b',
    secondaryColor: '#1e293b',
    tertiaryColor: '#020817',
    // attributeBackgroundColorOdd/Even are accepted here but mermaid's erDiagram renderer doesn't
    // actually use them — it computes each row's background from primaryColor via its own
    // internal lighten/darken formula regardless (odd rows land at ~92% lightness, i.e.
    // near-white, invisible against the equally-near-white attribute-name/type text on top of
    // it). The real fix is the `.row-rect-odd`/`.row-rect-even` CSS override in app.css, which
    // wins over mermaid's inline `fill="hsl(...)"` presentation attribute regardless of what's
    // configured here. Left set anyway in case a future mermaid version starts honoring them.
    attributeBackgroundColorOdd: '#020817',
    attributeBackgroundColorEven: '#0f172a',
    fontFamily: "'JetBrains Mono', ui-monospace, 'SF Mono', Consolas, monospace",
  },
})

// Mermaid's <svg> comes back as width="100%" with no height attribute — inside .diagram-zoomable
// (inline-block, no defined width of its own to resolve that percentage against), browsers fall
// back to the generic replaced-element default size (300x150 CSS px) instead of the diagram's
// real, much larger size. Baking width/height (read from the SVG's own viewBox) directly into the
// markup string — rather than setting them imperatively on the DOM node after the fact — makes
// the fix survive React re-applying dangerouslySetInnerHTML on a later render (e.g. when `scale`
// changes): an imperative post-hoc mutation gets silently wiped the next time React re-sets
// innerHTML from the original (still-unfixed) string, which is exactly what reintroduces this bug
// after a zoom click even though the source `svg` string itself never changes.
function withExplicitDimensions(svgMarkup: string): string {
  const match = svgMarkup.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/)
  if (!match) return svgMarkup
  const [, width, height] = match
  return svgMarkup.replace('<svg ', `<svg width="${width}" height="${height}" `)
}

export function ErDiagram({ source }: { source: string }) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [svgMarkup, setSvgMarkup] = useState<string | null>(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    let cancelled = false
    mermaid
      .render('er-diagram', source)
      .then(({ svg }) => {
        if (!cancelled) setSvgMarkup(withExplicitDimensions(svg))
      })
      .catch((error) => console.error('Diagram rendering failed:', error))
    return () => {
      cancelled = true
    }
  }, [source])

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return

    let dragging = false
    let startX = 0
    let startY = 0
    let scrollLeft = 0
    let scrollTop = 0

    function handlePointerDown(event: PointerEvent) {
      dragging = true
      viewport?.classList.add('grabbing')
      startX = event.clientX
      startY = event.clientY
      scrollLeft = viewport!.scrollLeft
      scrollTop = viewport!.scrollTop
    }
    function handlePointerUp() {
      dragging = false
      viewport?.classList.remove('grabbing')
    }
    function handlePointerMove(event: PointerEvent) {
      if (!dragging || !viewport) return
      viewport.scrollLeft = scrollLeft - (event.clientX - startX)
      viewport.scrollTop = scrollTop - (event.clientY - startY)
    }

    viewport.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('pointerup', handlePointerUp)
    viewport.addEventListener('pointermove', handlePointerMove)
    return () => {
      viewport.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('pointerup', handlePointerUp)
      viewport.removeEventListener('pointermove', handlePointerMove)
    }
  }, [])

  return (
    <>
      <div className="diagram-toolbar">
        <button type="button" aria-label="Zoom out" onClick={() => setScale((s) => Math.max(MIN_SCALE, s - STEP))}>
          –
        </button>
        <span className="zoom-level">{Math.round(scale * 100)}%</span>
        <button type="button" aria-label="Zoom in" onClick={() => setScale((s) => Math.min(MAX_SCALE, s + STEP))}>
          +
        </button>
        <button type="button" className="reset" aria-label="Reset zoom" onClick={() => setScale(1)}>
          Reset
        </button>
        <span className="hint">drag to pan · scroll to navigate at any zoom</span>
      </div>
      <div className="diagram-viewport" ref={viewportRef}>
        <div className="diagram-zoomable" style={{ transform: `scale(${scale})` }}>
          {svgMarkup ? (
            <div dangerouslySetInnerHTML={{ __html: svgMarkup }} />
          ) : (
            <p className="subtitle">Rendering diagram…</p>
          )}
        </div>
      </div>
    </>
  )
}
