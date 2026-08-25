// Formats the time between two ISO timestamps as a short, human-readable duration (e.g. "45s",
// "3m 12s", "1h 5m"). Callers decide when a duration is meaningful to show (e.g. only once a job
// has actually finished) -- this just formats whatever range it's given.
export function formatDuration(startIso: string, endIso: string): string {
  const totalSeconds = Math.max(0, Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 1000))

  if (totalSeconds < 60) return `${totalSeconds}s`

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes < 60) return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}
