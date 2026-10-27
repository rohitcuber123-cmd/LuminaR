/** Compatibility helper ignores legacy global labels. Route guards resolve real scope. */
export function destination(_role: string, from?: string): string { return workspaceDestination(from) }

/** Library membership, rather than global User.role, resolves the default after login. */
export function workspaceDestination(from?: string): string {
  if (!from || !from.startsWith('/') || from.startsWith('//') || from.includes('\\') || /^\/(?:login|signup|staff\/login|account\/continue|dashboard)(?:[/?#]|$)/.test(from)) return '/account/continue'
  // Authentication may replace the account that originally requested this URL.
  // Resolve current memberships before returning to an old tenant route.
  if (/^\/(?:staff\/libraries|libraries)\/[^/?#]+/.test(from) && !/^\/libraries\/register(?:[/?#]|$)/.test(from)) return `/account/continue?return_to=${encodeURIComponent(from)}`
  return from
}
