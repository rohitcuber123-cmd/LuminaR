import { useEffect, useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'
import { scrollToContentAnchor } from '../lib/paginationScroll'

const positions = new Map<string, number>()
export function RoutePresentation() {
  const location = useLocation(), navigation = useNavigationType(), previous = useRef(location)
  useEffect(() => {
    const original = history.scrollRestoration
    history.scrollRestoration = 'manual'
    return () => { history.scrollRestoration = original }
  }, [])
  useLayoutEffect(() => {
    const before = previous.current, pathChanged = before.pathname !== location.pathname
    previous.current = location
    let frame = 0, observer: ResizeObserver | undefined, timer: ReturnType<typeof setTimeout> | undefined
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const content = document.querySelector<HTMLElement>('.workspace-content, #main-content, main')
    const animation = pathChanged && !reduced ? content?.animate?.([{ opacity: 0, translate: '0 6px' }, { opacity: 1, translate: '0 0' }], { duration: 200, easing: 'cubic-bezier(.2,.65,.3,1)' }) : undefined
    const target = navigation === 'POP' ? positions.get(location.key) : undefined
    const restore = () => {
      if (target !== undefined) window.scrollTo({ top: target, behavior: 'instant' })
      else if (location.hash) {
        let id: string
        try { id = decodeURIComponent(location.hash.slice(1)) } catch { return }
        const element = document.getElementById(id)
        if (element) scrollToContentAnchor(element)
      } else if (pathChanged) window.scrollTo({ top: 0, behavior: 'instant' })
    }
    frame = requestAnimationFrame(() => {
      restore()
      if ((target !== undefined || location.hash) && typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(restore)
        observer.observe(document.body)
        timer = setTimeout(() => observer?.disconnect(), 1500)
      }
    })
    // User scrolling always wins over a delayed restore for async route content.
    const stop = () => observer?.disconnect()
    window.addEventListener('wheel', stop, { passive: true }); window.addEventListener('touchstart', stop, { passive: true }); window.addEventListener('keydown', stop)
    return () => {
      positions.set(location.key, window.scrollY)
      if (positions.size > 100) positions.delete(positions.keys().next().value!)
      cancelAnimationFrame(frame); observer?.disconnect(); clearTimeout(timer); animation?.cancel()
      window.removeEventListener('wheel', stop); window.removeEventListener('touchstart', stop); window.removeEventListener('keydown', stop)
    }
  }, [location, navigation])
  return null
}
