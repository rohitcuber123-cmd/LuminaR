import { PALETTES, type CoverVariant } from '@/data/books'
import { useEffect, useRef } from 'react'

interface BookCoverProps {
  title: string
  author?: string
  paletteIndex: number
  variant: CoverVariant
  className?: string
}

export function BookCover({ title, author, paletteIndex, variant, className = '' }: BookCoverProps) {
  const { bg, fg } = PALETTES[paletteIndex % PALETTES.length]
  const root=useRef<HTMLDivElement>(null)
  useEffect(()=>{
    const element=root.current;if(!element || typeof ResizeObserver==='undefined')return
    const measure=()=>{
      const width=element.clientWidth,height=element.clientHeight
      element.style.setProperty('--cover-type-scale','1')
      const content=element.querySelector<HTMLElement>('.book-cover-content'),copy=element.querySelector<HTMLElement>('.book-cover-copy'),brand=element.querySelector<HTMLElement>('.book-cover-brand')
      if(!content || !copy || !brand)return
      const space=height-2*width*.09-brand.getBoundingClientRect().height-8
      let scale=1
      for(let attempt=0;attempt<8 && copy.getBoundingClientRect().height>space;attempt++){
        scale*=.85;element.style.setProperty('--cover-type-scale',String(scale))
      }
    }
    const observer=new ResizeObserver(measure);observer.observe(element);measure()
    void document.fonts?.ready.then(()=>{if(root.current===element)measure()})
    return()=>observer.disconnect()
  },[title,author])

  return (
    <div
      ref={root}
      className={`book-cover-art relative aspect-[2/3] w-full overflow-hidden rounded-[2px] shadow-[0_1px_2px_rgba(0,0,0,0.08)] ${className}`}
      style={{ backgroundColor: bg, color: fg }}
      role="img" aria-label={`Cover for ${title}${author ? ' by '+author : ''}`}
    >
      {variant === 'circle' && (
        <div
          className="absolute -right-[18%] -top-[14%] aspect-square w-[75%] rounded-full opacity-90"
          style={{ backgroundColor: fg, mixBlendMode: 'overlay' }}
        />
      )}
      {variant === 'ring' && (
        <div
          className="absolute -bottom-[20%] -right-[16%] aspect-square w-[80%] rounded-full border-[14px] opacity-80"
          style={{ borderColor: fg }}
        />
      )}
      {variant === 'split' && (
        <div
          className="absolute inset-x-0 bottom-0 h-[42%] opacity-90"
          style={{ backgroundColor: fg, mixBlendMode: 'overlay' }}
        />
      )}
      {variant === 'stripe' && (
        <div
          className="absolute inset-y-0 right-0 w-[28%] opacity-90"
          style={{ backgroundColor: fg, mixBlendMode: 'overlay' }}
        />
      )}

      <div className="book-cover-content relative flex h-full flex-col justify-between p-[9%]">
        <span className="book-cover-brand font-display w-fit text-[0.6rem] leading-none opacity-70">LuminaR</span>
        <div className="book-cover-copy">
          <p className="book-cover-title font-display" title={title}>{title}</p>
          {author && <p className="book-cover-author mt-1.5 uppercase tracking-wide opacity-75" title={author}>{author}</p>}
        </div>
      </div>
    </div>
  )
}
