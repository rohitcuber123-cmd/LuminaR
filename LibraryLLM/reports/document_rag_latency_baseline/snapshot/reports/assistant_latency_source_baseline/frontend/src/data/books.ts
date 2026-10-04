export type CoverVariant = 'solid' | 'circle' | 'split' | 'ring' | 'stripe'

export interface CoverPalette {
  bg: string
  fg: string
}

export const PALETTES: CoverPalette[] = [
  { bg: '#e8c7c9', fg: '#191714' }, // rose
  { bg: '#c81d4f', fg: '#faf8f4' }, // magenta
  { bg: '#141414', fg: '#faf8f4' }, // black
  { bg: '#b3401f', fg: '#faf8f4' }, // brand red
  { bg: '#1f3a5f', fg: '#f4e9d8' }, // navy
  { bg: '#4c5b3f', fg: '#f4e9d8' }, // moss
  { bg: '#e7dcc5', fg: '#191714' }, // tan
  { bg: '#d98c3b', fg: '#191714' }, // ochre
  { bg: '#2b2b2b', fg: '#e0b84a' }, // charcoal / gold
  { bg: '#f4e9d8', fg: '#b3401f' }, // paper / red
]

export interface Book {
  id: string
  title: string
  author: string
  category: string
  year: number
  format: 'Book' | 'eBook' | 'Audiobook'
  copiesAvailable: number
  copiesTotal: number
  paletteIndex: number
  variant: CoverVariant
}

export const BOOKS: Book[] = [
  {
    id: 'b1',
    title: 'The Quiet Frontier',
    author: 'Nadia Ostrow',
    category: 'Fiction',
    year: 2023,
    format: 'Book',
    copiesAvailable: 3,
    copiesTotal: 5,
    paletteIndex: 0,
    variant: 'circle',
  },
  {
    id: 'b2',
    title: 'Signals & Noise',
    author: 'R. K. Osei',
    category: 'Science & Technology',
    year: 2021,
    format: 'Book',
    copiesAvailable: 0,
    copiesTotal: 4,
    paletteIndex: 4,
    variant: 'stripe',
  },
  {
    id: 'b3',
    title: 'Bone & Marrow',
    author: 'Vivian Cho',
    category: 'Mystery & Thriller',
    year: 2024,
    format: 'Book',
    copiesAvailable: 2,
    copiesTotal: 3,
    paletteIndex: 2,
    variant: 'ring',
  },
  {
    id: 'b4',
    title: 'A Century of Salt',
    author: 'Miguel Farias',
    category: 'History',
    year: 2019,
    format: 'Book',
    copiesAvailable: 6,
    copiesTotal: 6,
    paletteIndex: 7,
    variant: 'solid',
  },
  {
    id: 'b5',
    title: 'The Understory',
    author: 'Elin Vasko',
    category: 'Science & Technology',
    year: 2022,
    format: 'eBook',
    copiesAvailable: 12,
    copiesTotal: 12,
    paletteIndex: 5,
    variant: 'split',
  },
  {
    id: 'b6',
    title: 'Notes on Leaving',
    author: 'Priya Anand',
    category: 'Biography & Memoir',
    year: 2020,
    format: 'Book',
    copiesAvailable: 1,
    copiesTotal: 4,
    paletteIndex: 1,
    variant: 'solid',
  },
  {
    id: 'b7',
    title: 'The Long Ledger',
    author: 'Tobias Hahn',
    category: 'Business & Economics',
    year: 2018,
    format: 'Audiobook',
    copiesAvailable: 4,
    copiesTotal: 4,
    paletteIndex: 8,
    variant: 'ring',
  },
  {
    id: 'b8',
    title: 'Small Gods, Big Rooms',
    author: 'Casimir Duval',
    category: 'Philosophy',
    year: 2023,
    format: 'Book',
    copiesAvailable: 0,
    copiesTotal: 2,
    paletteIndex: 3,
    variant: 'circle',
  },
  {
    id: 'b9',
    title: 'Field Guide to Vanishing',
    author: 'Hana Sorel',
    category: "Children's",
    year: 2022,
    format: 'Book',
    copiesAvailable: 8,
    copiesTotal: 8,
    paletteIndex: 6,
    variant: 'stripe',
  },
  {
    id: 'b10',
    title: 'The Weight of Wings',
    author: 'Bram Ostergaard',
    category: 'Fantasy & Sci-Fi',
    year: 2024,
    format: 'Book',
    copiesAvailable: 5,
    copiesTotal: 7,
    paletteIndex: 9,
    variant: 'split',
  },
  {
    id: 'b11',
    title: 'Draftwork',
    author: 'Lena Ferreira',
    category: 'Art & Design',
    year: 2021,
    format: 'Book',
    copiesAvailable: 2,
    copiesTotal: 3,
    paletteIndex: 4,
    variant: 'ring',
  },
  {
    id: 'b12',
    title: 'Everything We Almost Kept',
    author: 'Jonas Reyes',
    category: 'Poetry',
    year: 2020,
    format: 'Book',
    copiesAvailable: 3,
    copiesTotal: 3,
    paletteIndex: 1,
    variant: 'stripe',
  },
]

export const NEW_ARRIVALS: Book[] = [BOOKS[4], BOOKS[9], BOOKS[10], BOOKS[7], BOOKS[2], BOOKS[8]]
