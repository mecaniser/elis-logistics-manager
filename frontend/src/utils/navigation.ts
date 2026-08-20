/**
 * Single source of truth for which routes exist for a given business type.
 *
 * Both the nav bar and the post-switch route guard read this, so a business
 * can never be left on a page its type does not support.
 */

export interface NavLink {
  path: string
  label: string
}

/** Routes only a logistics business has. Matched by prefix. */
const LOGISTICS_ONLY_PREFIXES = ['/trucks', '/settlements', '/repairs', '/vehicles']

const LOGISTICS_LINKS: NavLink[] = [
  { path: '/trucks', label: 'Vehicles' },
  { path: '/settlements', label: 'Settlements' },
  { path: '/repairs', label: 'Maintenance & Repairs' },
]

/** Nav links for a business type, in display order. */
export function getNavLinks(businessType?: string): NavLink[] {
  const links: NavLink[] = [{ path: '/', label: 'Dashboard' }]
  if (businessType === 'logistics') {
    links.push(...LOGISTICS_LINKS)
  }
  links.push({ path: '/accounting', label: 'Accounting' })
  links.push({ path: '/businesses', label: 'Businesses' })
  return links
}

/** False when the path belongs to a section the business type does not have. */
export function isRouteAvailable(pathname: string, businessType?: string): boolean {
  if (businessType === 'logistics') return true
  return !LOGISTICS_ONLY_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  )
}

/** Human-readable name of the section a path belongs to, for the redirect toast. */
export function sectionLabel(pathname: string): string {
  const match = [...LOGISTICS_LINKS].find(
    (link) => pathname === link.path || pathname.startsWith(`${link.path}/`)
  )
  if (match) return match.label
  if (pathname.startsWith('/vehicles')) return 'Vehicles'
  return 'That section'
}
