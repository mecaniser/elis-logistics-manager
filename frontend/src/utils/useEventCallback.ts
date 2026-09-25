import { useCallback, useLayoutEffect, useRef } from 'react'

/** Stable event handler using the latest committed state. Effects must still
 * declare the filters that should trigger a new request. */
export function useEventCallback<Args extends unknown[], Result>(callback: (...args: Args) => Result) {
  const latest = useRef(callback)
  useLayoutEffect(() => { latest.current = callback }, [callback])
  return useCallback((...args: Args) => latest.current(...args), [])
}
