import { useRef, useState } from 'react'

interface Props {
  file: File | null
  onFileSelected: (file: File | null) => void
}

export function Dropzone({ file, onFileSelected }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => event.key === 'Enter' && inputRef.current?.click()}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        const dropped = event.dataTransfer.files[0]
        if (dropped) onFileSelected(dropped)
      }}
      className={`mb-6 cursor-pointer rounded-sm border-2 border-dashed p-10 text-center transition-colors ${
        dragging ? 'border-primary bg-accent' : 'border-border bg-card'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
      />
      {file ? (
        <p className="text-sm text-foreground">{file.name}</p>
      ) : (
        <>
          <p className="text-sm text-foreground">Drag files here or click to browse</p>
          <p className="mt-1 text-xs text-muted-foreground">PDF, HTML, Markdown or plain text</p>
        </>
      )}
    </div>
  )
}
