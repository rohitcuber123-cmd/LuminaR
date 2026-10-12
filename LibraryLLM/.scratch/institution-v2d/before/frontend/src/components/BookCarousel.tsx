import { useRef, useState, useEffect, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface BookCarouselProps {
  children: ReactNode
  gap?: number // gap between cards in pixels
}

export function BookCarousel({ children, gap = 24 }: BookCarouselProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)
  const [isTransitioning, setIsTransitioning] = useState(false)

  const updateScrollButtons = () => {
    if (!scrollRef.current) return

    const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current
    
    setCanScrollLeft(scrollLeft > 10) // 10px threshold for rounding errors
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10)
  }

  useEffect(() => {
    updateScrollButtons()

    const scrollElement = scrollRef.current
    if (!scrollElement) return

    const handleScroll = () => {
      updateScrollButtons()
    }

    const observer = new ResizeObserver(() => {
      updateScrollButtons()
    })

    scrollElement.addEventListener('scroll', handleScroll, { passive: true })
    observer.observe(scrollElement)

    return () => {
      scrollElement.removeEventListener('scroll', handleScroll)
      observer.disconnect()
    }
  }, [children]) // Re-run when children change

  const scroll = (direction: 'left' | 'right') => {
    if (!scrollRef.current || isTransitioning) return

    setIsTransitioning(true)

    const container = scrollRef.current
    const cardWidth = 180 // width of each card
    const scrollAmount = (cardWidth + gap) * 4 // Scroll 4 cards at a time

    const targetScroll = direction === 'left'
      ? container.scrollLeft - scrollAmount
      : container.scrollLeft + scrollAmount

    container.scrollTo({
      left: targetScroll,
      behavior: 'smooth'
    })

    // Reset transitioning state after animation
    setTimeout(() => {
      setIsTransitioning(false)
      updateScrollButtons()
    }, 300)
  }

  return <div className="product-carousel">
    <div ref={scrollRef} className="product-book-rail flex overflow-x-auto no-scrollbar scroll-smooth" style={{gap:`${gap}px`}}>{children}</div>
    {(canScrollLeft || canScrollRight) && <div className="product-rail-controls" role="group" aria-label="Book rail navigation">
      <button onClick={()=>scroll('left')} disabled={!canScrollLeft || isTransitioning} aria-label="Scroll left"><ChevronLeft size={20}/></button>
      <button onClick={()=>scroll('right')} disabled={!canScrollRight || isTransitioning} aria-label="Scroll right"><ChevronRight size={20}/></button>
    </div>}
  </div>
}
