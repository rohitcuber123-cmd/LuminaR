import type { CoverVariant } from './books'

export interface Category {
  name: string
  count: number
  paletteIndex: number
  variant: CoverVariant
  coverTitle: string
}

export const CATEGORIES: Category[] = [
  { name: 'Fiction', count: 412, paletteIndex: 0, variant: 'circle', coverTitle: 'The Quiet Frontier' },
  { name: 'Non-Fiction', count: 287, paletteIndex: 6, variant: 'solid', coverTitle: 'Field Notes' },
  { name: 'Science & Technology', count: 198, paletteIndex: 4, variant: 'stripe', coverTitle: 'Signals & Noise' },
  { name: 'History', count: 233, paletteIndex: 7, variant: 'solid', coverTitle: 'A Century of Salt' },
  { name: 'Biography & Memoir', count: 156, paletteIndex: 1, variant: 'solid', coverTitle: 'Notes on Leaving' },
  { name: 'Philosophy', count: 94, paletteIndex: 3, variant: 'circle', coverTitle: 'Small Gods, Big Rooms' },
  { name: 'Poetry', count: 121, paletteIndex: 1, variant: 'stripe', coverTitle: 'Almost Kept' },
  { name: "Children's", count: 340, paletteIndex: 6, variant: 'stripe', coverTitle: 'Vanishing' },
  { name: 'Graphic Novels', count: 88, paletteIndex: 2, variant: 'ring', coverTitle: 'Ink & Panel' },
  { name: 'Mystery & Thriller', count: 176, paletteIndex: 2, variant: 'ring', coverTitle: 'Bone & Marrow' },
  { name: 'Fantasy & Sci-Fi', count: 209, paletteIndex: 9, variant: 'split', coverTitle: 'Weight of Wings' },
  { name: 'Art & Design', count: 67, paletteIndex: 4, variant: 'ring', coverTitle: 'Draftwork' },
  { name: 'Business & Economics', count: 102, paletteIndex: 8, variant: 'ring', coverTitle: 'The Long Ledger' },
  { name: 'Reference', count: 59, paletteIndex: 5, variant: 'split', coverTitle: 'The Understory' },
]
