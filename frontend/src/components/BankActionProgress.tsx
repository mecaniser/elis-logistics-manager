export default function BankActionProgress({message, started, now}: {message:string; started:number; now:number}) {
  return <span className="flex max-w-xs items-center justify-center gap-2" role="status" aria-live="polite">
    <span aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none" />
    <span className="text-left leading-5">{message} <span aria-hidden="true" className="whitespace-nowrap font-normal tabular-nums">{Math.max(0, Math.floor((now-started)/1000))}s</span></span>
  </span>
}
