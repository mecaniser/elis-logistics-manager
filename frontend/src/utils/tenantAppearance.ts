/**
 * Visual identity for a business. Three tenants named "Elis ..." are
 * indistinguishable as plain text, so every business gets a stable color
 * and a readable type label to go with its name.
 */

// Chosen to stay legible both as a swatch on the dark top bar and on white menu rows.
const TENANT_COLORS = [
  '#6366f1', // indigo
  '#10b981', // emerald
  '#f59e0b', // amber
  '#f43f5e', // rose
  '#0ea5e9', // sky
  '#8b5cf6', // violet
  '#14b8a6', // teal
  '#f97316', // orange
]

/** Stable per-business color. Same id always yields the same swatch. */
export function tenantColor(tenantId: number): string {
  return TENANT_COLORS[Math.abs(tenantId) % TENANT_COLORS.length]
}

const BUSINESS_TYPE_LABELS: Record<string, string> = {
  logistics: 'Logistics',
  tech: 'Tech',
  real_estate: 'Real Estate',
}

/** Short badge label, e.g. "Real Estate". Falls back to a humanized slug. */
export function businessTypeLabel(businessType?: string): string {
  if (!businessType) return ''
  return (
    BUSINESS_TYPE_LABELS[businessType] ||
    businessType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  )
}

/** Initials for a business name, e.g. "ELIS LOGISTICS LLC" -> "EL". */
export function tenantInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter((w) => !/^(llc|inc|ltd|co|corp)\.?$/i.test(w))
  const source = words.length > 0 ? words : name.trim().split(/\s+/)
  return source.slice(0, 2).map((w) => w[0] || '').join('').toUpperCase()
}
