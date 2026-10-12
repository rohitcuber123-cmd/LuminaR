/** Compatibility helper ignores legacy global labels. Route guards resolve real scope. */
export function destination(_role: string, from?: string): string { return workspaceDestination(from) }

/** Library membership, rather than global User.role, resolves the default after login. */
export function workspaceDestination(from?: string): string {
  if (!from || !from.startsWith('/') || from.startsWith('//') || from.includes('\\') || /^\/(?:login|signup|staff\/login|account\/continue|dashboard)(?:[/?#]|$)/.test(from)) return '/account/continue'
  return from
}
