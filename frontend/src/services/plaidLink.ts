type PlaidHandler = { open: () => void; destroy: () => void }
type PlaidFactory = { create: (options: { token: string; receivedRedirectUri?: string; onSuccess: (publicToken: string | null) => void; onExit: () => void }) => PlaidHandler }
declare global { interface Window { Plaid?: PlaidFactory } }
let plaidScript: Promise<void> | null = null
export function loadPlaidLink(): Promise<void> {
  if (window.Plaid) return Promise.resolve()
  if (!plaidScript) plaidScript = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.plaid.com/link/v2/stable/link-initialize.js'
    script.async = true
    script.onload = () => window.Plaid ? resolve() : reject(new Error('Bank connection could not open.'))
    script.onerror = () => reject(new Error('Bank connection could not load.'))
    document.head.appendChild(script)
  }).catch(error => { plaidScript = null; throw error })
  return plaidScript!
}
