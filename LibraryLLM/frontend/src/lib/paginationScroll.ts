/**
 * Shared pagination scroll helper.
 * Scrolls to the logical results anchor, accounting for the sticky top nav
 * (64px) plus a small visual buffer (8px).
 *
 * Only call this after user-initiated pagination (Next / Previous / page N).
 * Respects prefers-reduced-motion: uses instant scroll when motion is reduced.
 */

const HEADER_HEIGHT = 64 // px – matches .global-header height
const VISUAL_BUFFER = 8  // px – small gap so anchor isn't flush with header
let cancelPendingScroll: (() => void) | undefined

/**
 * Scroll to an element, offset by the sticky header.
 * @param anchor  - CSS selector string or HTMLElement
 * @param smooth  - override; undefined = auto-detect from prefers-reduced-motion
 */
export function scrollToContentAnchor(
  anchor: string | HTMLElement | null,
  smooth?: boolean,
): void {
  cancelPendingScroll?.()
  const routePath = window.location.pathname
  const findAnchor = () =>
    anchor instanceof HTMLElement
      ? anchor
      : anchor
        ? anchor.split(',').map(selector => document.querySelector<HTMLElement>(selector.trim())).find(Boolean)
        : null

  function align(behavior: ScrollBehavior) {
    if (window.location.pathname !== routePath) return
    const el = findAnchor()
    if (!el) return
    const rect = el.getBoundingClientRect()
    const absoluteTop = rect.top + window.scrollY
    const header = document.querySelector<HTMLElement>('.global-header')
    const headerHeight = header?.getBoundingClientRect().height || HEADER_HEIGHT
    const target = Math.max(0, absoluteTop - headerHeight - VISUAL_BUFFER)
    window.scrollTo({ top: target, behavior })
  }
  align(resolveScrollBehavior(smooth))
  // Loading placeholders can temporarily remove the results anchor or shorten
  // the page. Align again when async pagination commits its final geometry.
  if (typeof anchor !== 'string' || typeof ResizeObserver === 'undefined') return
  const observer = new ResizeObserver(() => align('instant'))
  observer.observe(document.body)
  const changes = typeof MutationObserver === 'undefined' ? undefined : new MutationObserver(() => align('instant'))
  changes?.observe(document.body, { childList: true, subtree: true })
  const cancel = () => {
    observer.disconnect(); changes?.disconnect(); clearTimeout(timer)
    window.removeEventListener('wheel', cancel); window.removeEventListener('touchstart', cancel); window.removeEventListener('keydown', cancel); window.removeEventListener('pointerdown', cancel)
    if (cancelPendingScroll === cancel) cancelPendingScroll = undefined
  }
  const timer = setTimeout(cancel, changes ? 10000 : 1800)
  window.addEventListener('wheel', cancel, { passive: true }); window.addEventListener('touchstart', cancel, { passive: true }); window.addEventListener('keydown', cancel); window.addEventListener('pointerdown', cancel)
  cancelPendingScroll = cancel
}

/** Resolve scroll behavior respecting prefers-reduced-motion. */
function resolveScrollBehavior(override?: boolean): ScrollBehavior {
  if (override === false) return 'instant'
  const reduced = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)')?.matches
    : false
  return reduced ? 'instant' : 'smooth'
}

/**
 * Returns a stable callback that scrolls to the anchor after a rAF tick.
 * rAF ensures DOM has settled after React commits the state change.
 */
export function usePaginationScroll(anchorSelector: string): () => void {
  return function scrollOnPageChange() {
    requestAnimationFrame(() => {
      scrollToContentAnchor(anchorSelector)
    })
  }
}
