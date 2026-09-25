import { isAxiosError } from 'axios'

/** Normalize unknown thrown values before presenting server errors to an operator. */
export function apiError(error: unknown) {
  const message = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  if (!isAxiosError<Record<string, unknown>>(error)) return { message, response: undefined }
  const data = error.response?.data
  const text = (value: unknown): string | undefined => typeof value === 'string' ? value : value == null ? undefined : JSON.stringify(value)
  return { message, response: error.response ? { status: error.response.status, data: { detail: text(data?.detail), message: text(data?.message) } } : undefined }
}
