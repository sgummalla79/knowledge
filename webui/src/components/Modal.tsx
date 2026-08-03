import type { ReactNode } from 'react'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}

export function Modal({ title, onClose, children, wide }: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} onClick={(event) => event.stopPropagation()}>
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  )
}
