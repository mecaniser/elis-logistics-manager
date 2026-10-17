export type AssistantConnectionState = 'checking' | 'connected' | 'outdated' | 'unavailable' | 'unconfigured'

export default function BankAssistantStatus({ state, version, hasDrafts, onSettings }: {
  state: AssistantConnectionState; version: string; hasDrafts: boolean; onSettings: () => void
}) {
  const connected = state === 'connected'
  const label = connected ? `Connected${version ? ` · ${version}` : ''}` : state === 'checking' ? 'Checking connection…' : state === 'outdated' ? 'Update needed' : state === 'unconfigured' ? 'Not connected' : 'Unavailable in this browser'
  return <section aria-label="Truliant form assistant" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div>
      <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold text-slate-950">Truliant form assistant</h2><span role="status" className={`rounded-full px-2.5 py-1 text-xs font-semibold ${connected ? 'bg-emerald-50 text-emerald-800' : state === 'checking' ? 'bg-slate-100 text-slate-600' : 'bg-amber-50 text-amber-900'}`}>{label}</span></div>
      <p className="mt-2 text-sm text-slate-600">{connected ? hasDrafts ? 'Open a transfer below to review it and approve preparation in the extension.' : 'Choose Review transfers above to create a draft, then approve preparation in the extension.' : 'Connect the Chrome extension to review and prepare Truliant forms.'}</p>
    </div>
    <button type="button" onClick={onSettings} className="min-h-11 whitespace-nowrap rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-800 hover:bg-slate-50">{connected ? 'Assistant settings' : 'Connect or troubleshoot'}</button>
  </section>
}
