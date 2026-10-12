import requirements from '../../../backend/schemas/event_publish_requirements.json'
import type { EventCategory, EventInput } from './events'

export type EditorSection = 'books' | 'schedule'
export interface EventPreset {
  helper: string
  order: EditorSection[]
  booksMode: 'prominent' | 'optional' | 'collapsed' | 'hidden'
  booksLabel: string
  booksHelper: string
  startLabel: string
  endLabel: string
  scheduleCollapsed: boolean
  locationHelper: string
  summaryLabel: string
  descriptionLabel: string
  descriptionHelper: string
  defaultFeatured: boolean
}
const generic: EventPreset = {
  helper: 'Publish a library event or announcement.', order: ['schedule', 'books'], booksMode: 'optional',
  booksLabel: 'Related Books', booksHelper: 'Optionally link catalogue books. Selected order is preserved.',
  startLabel: 'Start date and time', endLabel: 'End date and time', scheduleCollapsed: false,
  locationHelper: 'Optional venue or library area.', summaryLabel: 'Summary', descriptionLabel: 'Description',
  descriptionHelper: 'Plain text. Add the details readers need.', defaultFeatured: false,
}
function preset(overrides: Partial<EventPreset>): EventPreset { return { ...generic, ...overrides } }
export const EVENT_PRESETS: Record<EventCategory, EventPreset> = {
  NEW_ARRIVALS: preset({ helper: 'Highlight the latest additions to your catalogue.', order: ['books', 'schedule'], booksMode: 'prominent', booksLabel: 'New Books', booksHelper: 'Choose the new books you want to highlight. Select at least one to publish; drafts can have none.', scheduleCollapsed: true }),
  BOOK_SALE: preset({ helper: 'Announce an offline library book sale.', startLabel: 'Sale Starts', endLabel: 'Sale Ends', booksLabel: 'Books in Sale', booksHelper: 'Optionally highlight catalogue books included in the sale.', locationHelper: 'Where the sale takes place. Required to publish.' }),
  WORKSHOP: preset({ helper: 'Share a workshop, its venue and what participants will learn.', startLabel: 'Workshop Starts', endLabel: 'Workshop Ends', locationHelper: 'Workshop venue. Required to publish.', descriptionHelper: 'Describe the workshop and what participants will learn. Required to publish.' }),
  AUTHOR_EVENT: preset({ helper: 'Introduce an author visit or talk. Include the speaker in the summary or description.', startLabel: 'Author Event Starts', endLabel: 'Author Event Ends', summaryLabel: 'Summary / Author or Speaker', descriptionLabel: 'Description / Speaker Details', descriptionHelper: 'Include the author or speaker name, topic and visit details.' }),
  READING_CLUB: preset({ helper: 'Choose the books your reading club will discuss.', order: ['books', 'schedule'], booksMode: 'prominent', booksLabel: 'Reading Club Books', booksHelper: 'Choose the featured reading club book, or several books. Select at least one to publish.', startLabel: 'Meeting Starts', endLabel: 'Meeting Ends' }),
  COMMUNITY_EVENT: preset({ helper: 'Bring readers together for a community event.', startLabel: 'Community Event Starts', endLabel: 'Community Event Ends' }),
  LIBRARY_PROGRAM: preset({ helper: 'Share a library program and its schedule.', startLabel: 'Program Starts', endLabel: 'Program Ends' }),
  LIBRARY_NOTICE: preset({ helper: 'Publish a concise library announcement. Dates, location and books are optional.', booksMode: 'collapsed', scheduleCollapsed: true }),
  CLOSURE: preset({ helper: 'Explain a temporary library closure and when service resumes.', booksMode: 'hidden', startLabel: 'Closure Starts', endLabel: 'Reopens / Closure Ends', descriptionLabel: 'Reason / Description', descriptionHelper: 'Explain why the library is closing. Required to publish.', locationHelper: 'Optional when the closure applies to the whole library.' }),
  EXHIBITION: preset({ helper: 'Introduce an exhibition, its dates and venue.', startLabel: 'Exhibition Starts', endLabel: 'Exhibition Ends' }),
  OTHER: preset({ helper: 'Use the full event form for anything that does not fit another type.' }),
}
type Requirement = { fields: Record<string, string>; min_books: number; books_error?: string }
export const EVENT_PUBLISH_REQUIREMENTS: Record<EventCategory, Requirement> = requirements
export interface EventFieldError { field: keyof EventInput; message: string }
export function publishErrors(event: EventInput): EventFieldError[] {
  const rule = EVENT_PUBLISH_REQUIREMENTS[event.category]
  const errors: EventFieldError[] = Object.entries(rule.fields).filter(([field]) => {
    const value = event[field as keyof EventInput]
    return !value || typeof value === 'string' && !value.trim()
  }).map(([field, message]) => ({ field: field as keyof EventInput, message }))
  if (event.related_work_ids.length < rule.min_books) errors.push({ field: 'related_work_ids', message: rule.books_error! })
  return errors
}
export function baseErrors(event: EventInput): EventFieldError[] {
  const errors: EventFieldError[] = []
  if (event.title.trim().length < 3) errors.push({ field: 'title', message: 'Enter a title with at least 3 characters.' })
  for (const [field, max] of [['title', 140], ['summary', 300], ['description', 5000], ['location', 200]] as const)
    if ((event[field] || '').trim().length > max) errors.push({ field, message: `${field} must be no more than ${max} characters.` })
  for (const field of ['start_at', 'end_at'] as const)
    if (event[field] && !Number.isFinite(new Date(event[field]!).getTime())) errors.push({ field, message: 'Enter a valid date and time.' })
  if (event.end_at && (!event.start_at || new Date(event.end_at) < new Date(event.start_at)))
    errors.push({ field: 'end_at', message: 'End time cannot be before start time. Provide a start time.' })
  if (event.related_work_ids.length > 12) errors.push({ field: 'related_work_ids', message: 'Select no more than 12 related books.' })
  return errors
}
export function requiresPublishedValidation(old: EventInput, current: EventInput) {
  return old.category !== current.category || publishErrors(old).length === 0
}
