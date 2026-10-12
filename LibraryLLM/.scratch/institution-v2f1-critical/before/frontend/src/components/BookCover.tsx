import { PALETTES, type CoverVariant } from '@/data/books'

interface BookCoverProps {
  title: string
  author?: string
  paletteIndex: number
  variant: CoverVariant
  className?: string
}

export function BookCover({ title, author, paletteIndex, variant, className = '' }: BookCoverProps) {
  const { bg, fg } = PALETTES[paletteIndex % PALETTES.length]

  return (
    <div
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
        <span className="book-cover-brand font-display w-fit text-[0.6rem] leading-none">LuminaR</span>
        <div className="book-cover-copy relative">
          <div className="book-cover-text-scrim absolute inset-0 pointer-events-none" aria-hidden="true" style={{backgroundColor:bg}} />
          <p className="book-cover-title relative font-display" title={title}>{title}</p>
          {author && <p className="book-cover-author relative mt-1.5 text-[0.62rem] uppercase tracking-wide" title={author}>{author}</p>}
        </div>
      </div>
    </div>
  )
}
