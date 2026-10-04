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
      className={`relative aspect-[2/3] w-full overflow-hidden rounded-[2px] shadow-[0_1px_2px_rgba(0,0,0,0.08)] ${className}`}
      style={{ backgroundColor: bg, color: fg }}
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

      <div className="relative flex h-full flex-col justify-between p-[9%]">
        <span className="font-display text-[0.6rem] leading-none opacity-70">LuminaR</span>
        <div>
          <p className="font-display text-[clamp(0.8rem,1.6vw,1.15rem)] leading-[1.05]">{title}</p>
          {author && <p className="mt-1.5 text-[0.62rem] uppercase tracking-wide opacity-75">{author}</p>}
        </div>
      </div>
    </div>
  )
}
