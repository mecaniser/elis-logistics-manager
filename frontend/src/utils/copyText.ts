/** Start clipboard.write during the click, even when fetching the text takes time
 * (Safari requires the user gesture at the point the write is requested). */
export async function copyText(value: string | Promise<string>): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      if (typeof value !== 'string' && typeof ClipboardItem !== 'undefined') {
        await navigator.clipboard.write([new ClipboardItem({
          'text/plain': value.then((text) => new Blob([text], { type: 'text/plain' })),
        })])
        return true
      }
      await navigator.clipboard.writeText(await value)
      return true
    }
  } catch {
    // Retry using the legacy clipboard path below, without logging the value.
  }
  let textarea: HTMLTextAreaElement | undefined
  try {
    const text = await value
    textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    textarea?.remove()
  }
}
