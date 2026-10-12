export type NavLink = { label: string; to: string }
/** Compatibility helper: global identity labels never generate management navigation. */
export function getRoleNavLinks(role?: string): NavLink[] {
  return role ? [{ label: 'My Libraries', to: '/account/libraries' }] : []
}
