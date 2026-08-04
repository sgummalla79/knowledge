export class ApiError extends Error {
  status: number
  code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

// Shared by the bearer-token client (client.ts) and the session+CSRF auth calls (auth.ts) — both
// hit the same {"error": {"code", "message"}} envelope every route in this app returns on failure.
export async function parseErrorBody(response: Response): Promise<{ message: string; code?: string }> {
  try {
    const body = (await response.json()) as { error?: { message?: string; code?: string } }
    if (body.error?.message) return { message: body.error.message, code: body.error.code }
  } catch {
    // Non-JSON error body (e.g. a proxy/500 page) — fall through to the generic message below.
  }
  return { message: `Request failed with status ${response.status}` }
}
