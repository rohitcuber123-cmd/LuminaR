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

  return (
    <div className="relative">
      {/* Left Arrow */}
      {canScrollLeft && (
        <button
          onClick={() => scroll('left')}
          disabled={isTransitioning}
          className="absolute left-0 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-paper shadow-[0_4px_12px_rgba(0,0,0,0.15)] transition-all hover:bg-brand hover:text-paper hover:shadow-[0_6px_16px_rgba(0,0,0,0.2)] disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Scroll left"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
      )}

      {/* Carousel Container */}
      <div
        ref={scrollRef}
        className="flex gap-6 overflow-x-auto pb-4 no-scrollbar scroll-smooth"
        style={{ gap: `${gap}px` }}
      >
        {children}
      </div>

      {/* Right Arrow */}
      {canScrollRight && (
        <button
          onClick={() => scroll('right')}
          disabled={isTransitioning}
          className="absolute right-0 top-1/2 z-10 translate-x-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-paper shadow-[0_4px_12px_rgba(0,0,0,0.15)] transition-all hover:bg-brand hover:text-paper hover:shadow-[0_6px_16px_rgba(0,0,0,0.2)] disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Scroll right"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      )}
    </div>
  )
}
