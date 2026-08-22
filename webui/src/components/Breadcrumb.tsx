import { Fragment } from 'react'
import { Link } from 'react-router-dom'

export interface Crumb {
  label: string
  to?: string
}

export function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <div className="mb-3 text-[13px] text-muted-foreground">
      {items.map((item, index) => (
        <Fragment key={index}>
          {index > 0 && <span className="mx-1.5">/</span>}
          {item.to ? (
            <Link to={item.to} className="hover:text-foreground">
              {item.label}
            </Link>
          ) : (
            <span className="text-foreground">{item.label}</span>
          )}
        </Fragment>
      ))}
    </div>
  )
}
