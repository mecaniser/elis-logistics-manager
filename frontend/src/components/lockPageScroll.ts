let locks = 0
let restorePage: (() => void) | undefined

/** Keep the page fixed until the last overlapping bank overlay closes. */
export function lockPageScroll() {
  if (locks === 0) {
    const body = document.body
    const root = document.documentElement
    const scrollX = window.scrollX
    const scrollY = window.scrollY
    const previous = { overflow: body.style.overflow, position: body.style.position, top: body.style.top, left: body.style.left, width: body.style.width, paddingRight: body.style.paddingRight, rootOverflow: root.style.overflow }
    const scrollbarWidth = window.innerWidth - root.clientWidth
    if (scrollbarWidth > 0) body.style.paddingRight = `${parseFloat(getComputedStyle(body).paddingRight) + scrollbarWidth}px`
    root.style.overflow = 'hidden'
    body.style.overflow = 'hidden'
    body.style.position = 'fixed'
    body.style.top = `-${scrollY}px`
    body.style.left = `-${scrollX}px`
    body.style.width = '100%'
    restorePage = () => {
      body.style.overflow = previous.overflow
      body.style.position = previous.position
      body.style.top = previous.top
      body.style.left = previous.left
      body.style.width = previous.width
      body.style.paddingRight = previous.paddingRight
      root.style.overflow = previous.rootOverflow
      window.scrollTo({ left: scrollX, top: scrollY, behavior: 'instant' })
    }
  }
  locks += 1
  let released = false
  return () => {
    if (released) return
    released = true
    locks -= 1
    if (locks === 0) { restorePage?.(); restorePage = undefined }
  }
}
