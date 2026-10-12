import { request, ApiError } from './api'

export type LibraryRole = 'GENERAL_USER' | 'LIBRARIAN' | 'ADMIN'
export type Membership = { membership_id: string; library_id: string; user_id: number; role: LibraryRole; status: 'ACTIVE' | 'SUSPENDED' | 'REMOVED'; is_owner: boolean; joined_at: string }
export type Library = { library_id: string; name: string; slug: string; description: string | null; library_type: 'PUBLIC_LIBRARY' | 'PRIVATE_INSTITUTION'; access_mode: 'PUBLIC' | 'PRIVATE_CODE'; contact_email?: string | null; phone?: string | null; address?: { line1?: string; line2?: string; city?: string; region?: string; country?: string; postal_code?: string } | null; membership?: Membership | null }
export type LibraryContext = { library: Library; membership: Membership }
export type Page<T> = { results: T[]; total?: number; offset?: number; limit?: number; has_more?: boolean }
export type Invitation = { invitation_id: string; library_id: string; library_name?: string; email_normalized: string; role: LibraryRole; status: string; invited_by_user_id: number; expires_at: string; requires_token?: boolean }
export type MemberRow = Membership & { name: string; email: string }
export type AccessSettings = { access_code_set: boolean; access_code_changed_at: string | null; access_code_changed_by: number | null }

// Canonical reads also reconcile under the library mutation lock. Keep one
// browser's requests to the same tenant ordered; other libraries remain independent.
const tenantRequests = new Map<string, Promise<unknown>>()
export function institutionApi<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  const tenant = path.match(/^\/libraries\/([0-9a-f-]{36})(?:\/|$)/i)?.[1]
  const session = localStorage.getItem('luminar_token')
  const send = async () => {
    for (let attempt = 0; ; attempt++) {
      if (signal?.aborted || session !== localStorage.getItem('luminar_token')) throw new DOMException('Request context changed.', 'AbortError')
      try {
        return await request<T>('/api' + path, { method, cache: 'no-store', signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
      } catch (error) {
        // A cancelled browser read can leave accepted server reconciliation
        // briefly running. Retry only reads, with the original scope/session.
        if (method !== 'GET' || !(tenant || path.startsWith('/me/libraries')) || !(error instanceof ApiError) || error.status !== 503 || attempt >= 2) throw error
        await new Promise<void>((resolve, reject) => {
          const abort = () => { clearTimeout(timer); reject(new DOMException('Request context changed.', 'AbortError')) }
          const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve() }, 300 * (attempt + 1))
          signal?.addEventListener('abort', abort, { once: true })
          if (signal?.aborted) abort()
        })
      }
    }
  }
  if (!tenant) return send()
  const pending = (tenantRequests.get(tenant) || Promise.resolve()).catch(() => undefined).then(send)
  tenantRequests.set(tenant, pending)
  void pending.finally(() => { if (tenantRequests.get(tenant) === pending) tenantRequests.delete(tenant) }).catch(() => undefined)
  return pending
}

export function invitationLink(invitationId: string, token: string) {
  // URL fragments are not transmitted in HTTP requests or Referer headers.
  return `${window.location.origin}/invitations/${encodeURIComponent(invitationId)}#token=${encodeURIComponent(token)}`
}
