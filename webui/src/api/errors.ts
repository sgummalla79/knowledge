export class ApiError extends Error {
  status: number
  code?: string
  field?: string

  constructor(message: string, status: number, code?: string, field?: string) {
    super(message)
    this.status = status
    this.code = code
    this.field = field
  }
}

// Shared by every API call in this app (client.ts's cookie+CSRF fetch wrapper, auth.ts) — all hit
// the same {"error": {"code", "message", "field"}} envelope every route returns on failure.
export async function parseErrorBody(response: Response): Promise<{ message: string; code?: string; field?: string }> {
  try {
    const body = (await response.json()) as { error?: { message?: string; code?: string; field?: string } }
    if (body.error?.message) return { message: body.error.message, code: body.error.code, field: body.error.field }
  } catch {
    // Non-JSON error body (e.g. a proxy/500 page) — fall through to the generic message below.
  }
  return { message: `Request failed with status ${response.status}` }
}
