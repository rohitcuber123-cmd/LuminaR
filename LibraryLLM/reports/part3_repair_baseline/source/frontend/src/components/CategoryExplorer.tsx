import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { BookCover } from '@/components/BookCover'
import { getCategories, type Category } from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'

const ROTATION_INTERVAL = 120000 // 2 minutes
const DISPLAY_COUNT = 13 // Number of categories to show at once

// Fisher-Yates shuffle algorithm
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

// Select random subset avoiding consecutive duplicates
function selectRandomSubset(
  allCategories: Category[],
  count: number,
  previousSet: Set<string>
): Category[] {
  if (allCategories.length <= count) {
    return shuffleArray(allCategories)
  }

  // Separate categories into previously shown and new
  const notInPrevious = allCategories.filter(cat => !previousSet.has(cat.name))
  const inPrevious = allCategories.filter(cat => previousSet.has(cat.name))

  // Prefer categories not shown in previous rotation
  const shuffledNew = shuffleArray(notInPrevious)
  const shuffledOld = shuffleArray(inPrevious)

  // Take as many new categories as possible, fill with old if needed
  const selected = [
    ...shuffledNew.slice(0, Math.min(count, shuffledNew.length)),
    ...shuffledOld.slice(0, Math.max(0, count - shuffledNew.length))
  ].slice(0, count)

  return shuffleArray(selected)
}

export function CategoryExplorer() {
  const [allCategories, setAllCategories] = useState<Category[]>([])
  const [displayedCategories, setDisplayedCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [isTransitioning, setIsTransitioning] = useState(false)
  
  const previousSetRef = useRef<Set<string>>(new Set())
  const navigate = useNavigate()

  // Fetch all categories once
  useEffect(() => {
    let isMounted = true

    async function fetchCategories() {
      try {
        setLoading(true)
        const response = await getCategories()
        if (isMounted) {
          if (response && response.categories && response.categories.length > 0) {
            setAllCategories(response.categories)
            // Show initial selection immediately
            const initial = selectRandomSubset(response.categories, DISPLAY_COUNT, new Set())
            setDisplayedCategories(initial)
            previousSetRef.current = new Set(initial.map(c => c.name))
          } else {
            setError(true)
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(true)
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    fetchCategories()

    return () => {
      isMounted = false
    }
  }, [])

  // Rotate categories periodically
  useEffect(() => {
    if (allCategories.length === 0) return

    const interval = setInterval(() => {
      // Fade out
      setIsTransitioning(true)

      setTimeout(() => {
        // Select new categories
        const newSelection = selectRandomSubset(
          allCategories,
          DISPLAY_COUNT,
          previousSetRef.current
        )
        setDisplayedCategories(newSelection)
        setActiveIndex(0) // Reset to first category
        previousSetRef.current = new Set(newSelection.map(c => c.name))

        // Fade in
        setTimeout(() => {
          setIsTransitioning(false)
        }, 50)
      }, 300)
    }, ROTATION_INTERVAL)

    return () => clearInterval(interval)
  }, [allCategories])

  if (loading) {
    return (
      <section className="relative overflow-hidden border-t border-line bg-panel py-20 md:py-28">
        <h2 className="font-display mb-12 text-center text-[0.8rem] tracking-[0.25em] text-ink-soft md:mb-16">
          Browse by Category
        </h2>
        <div className="mx-auto flex max-w-[40rem] flex-col items-center gap-4 px-6 opacity-40">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-8 w-48 rounded bg-line animate-pulse" />
          ))}
        </div>
      </section>
    )
  }

  if (error || displayedCategories.length === 0) {
    return (
      <section className="relative overflow-hidden border-t border-line bg-panel py-20 md:py-28">
        <h2 className="font-display mb-12 text-center text-[0.8rem] tracking-[0.25em] text-ink-soft md:mb-16">
          Browse by Category
        </h2>
        <div className="text-center text-ink-soft">
          <p>Categories currently unavailable.</p>
        </div>
      </section>
    )
  }

  const activeCategory = displayedCategories[activeIndex] || displayedCategories[0]
  const corner = activeIndex % 2 === 0 ? 'top-right' : 'bottom-left'
  const activeBook = activeCategory.preview_book

  function handleCategoryClick(categoryName: string) {
    navigate(`/catalog?category=${encodeURIComponent(categoryName)}`)
  }

  return (
    <section className="relative overflow-hidden border-t border-line bg-panel py-20 md:py-28">
      <h2 className="font-display mb-12 text-center text-[0.8rem] tracking-[0.25em] text-ink-soft md:mb-16">
        Browse by Category
      </h2>

      <div className="relative mx-auto max-w-[40rem] px-6">
        <div
          className={`pointer-events-none absolute z-0 hidden w-[190px] transition-all duration-500 ease-out md:block ${
            corner === 'top-right' ? '-right-[210px] -top-10 md:-right-[230px]' : '-left-[210px] bottom-0 md:-left-[230px]'
          }`}
          style={{
            opacity: isTransitioning ? 0 : 1,
            transform: isTransitioning ? 'scale(0.95)' : 'scale(1)',
            transition: 'opacity 300ms ease-out, transform 300ms ease-out'
          }}
          key={activeCategory.name}
        >
          {activeBook ? (
            <div className="animate-[fadeIn_0.5s_ease-out] pointer-events-auto">
              <Link to={`/book/${activeBook.work_id}`} className="block transition-transform hover:-translate-y-2 hover:scale-[1.02]">
                <BookCover 
                  title={activeBook.title}
                  author={activeBook.authors || 'Unknown Author'}
                  paletteIndex={activeBook.book_id % PALETTES.length} 
                  variant={['circle', 'ring', 'split', 'stripe'][activeBook.book_id % 4] as CoverVariant} 
                  className="shadow-[0_18px_40px_rgba(0,0,0,0.15)]"
                />
              </Link>
            </div>
          ) : (
            <div className="animate-[fadeIn_0.5s_ease-out]">
              <div className="aspect-[2/3] w-full rounded-[2px] bg-line border border-dashed border-ink-soft/30 flex items-center justify-center p-4 text-center">
                <span className="font-display text-[0.8rem] text-ink-soft opacity-50">No preview available</span>
              </div>
            </div>
          )}
        </div>

        <ul 
          className="relative z-10 text-center"
          style={{
            opacity: isTransitioning ? 0 : 1,
            transform: isTransitioning ? 'translateY(10px)' : 'translateY(0)',
            transition: 'opacity 300ms ease-out, transform 300ms ease-out'
          }}
        >
          {displayedCategories.map((cat, i) => (
            <li key={cat.name}>
              <button
                onMouseEnter={() => setActiveIndex(i)}
                onFocus={() => setActiveIndex(i)}
                onClick={() => handleCategoryClick(cat.name)}
                className={`font-display w-full py-1.5 text-[clamp(1.3rem,4.4vw,2.1rem)] leading-none tracking-tight transition-all duration-300 ${
                  i === activeIndex ? 'text-brand' : 'text-ink/25 hover:text-ink/50'
                }`}
              >
                {cat.name}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <p 
        className="mt-12 text-center text-[0.75rem] text-ink-soft"
        style={{
          opacity: isTransitioning ? 0 : 1,
          transition: 'opacity 300ms ease-out'
        }}
      >
        {activeCategory.count.toLocaleString()} titles in <span className="text-ink">{activeCategory.name}</span>
      </p>
    </section>
  )
}
