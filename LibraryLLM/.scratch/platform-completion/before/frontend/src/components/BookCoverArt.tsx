import { useState } from 'react'
import { BookCover } from './BookCover'
import { PALETTES, type CoverVariant } from '../data/books'
/** One cover renderer for global, owned, saved and discovery representations. */
export function BookCoverArt({ title, author, seed, url, className = '' }: { title: string; author: string; seed: number; url?: string | null; className?: string }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const variants: CoverVariant[] = ['circle','ring','split','stripe']
  return url && /^https?:\/\//.test(url) && failedUrl !== url ? <img src={url} alt={`Cover for ${title}`} loading="lazy" onError={() => setFailedUrl(url)}
    className={`aspect-[2/3] w-full rounded-[2px] object-cover ${className}`} /> :
    <BookCover title={title} author={author} paletteIndex={seed % PALETTES.length} variant={variants[seed % variants.length]} className={className} />
}
