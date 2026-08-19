const ROLES = [
  { role: 'Admin', description: 'Manage members, roles, library access, and embedding models.' },
  { role: 'Contributor', description: 'Upload and edit documents; can’t manage members.' },
  { role: 'Viewer', description: 'Browse and search only the shelves assigned to them.' },
]

export function RoleLegend() {
  return (
    <div className="rounded-sm bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold text-foreground">What each role can do</h3>
      <dl className="flex flex-col gap-2.5">
        {ROLES.map((entry) => (
          <div key={entry.role}>
            <dt className="text-[13px] font-semibold text-foreground">{entry.role}</dt>
            <dd className="text-[13px] text-muted-foreground">{entry.description}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
