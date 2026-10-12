import { coreRequest } from '../lib/api'
/** Shared transport and date formatting; legacy dashboard mutation helpers were removed. */
export const api = coreRequest
export function dateValue(value?: string) {
  if (!value) return NaN
  return Date.parse(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`)
}
