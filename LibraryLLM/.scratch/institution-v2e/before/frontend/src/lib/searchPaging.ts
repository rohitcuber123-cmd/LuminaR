export const SEARCH_PAGE_SIZE = 10
export function searchPaging(params: URLSearchParams) {
  const raw = Number(params.get('offset') || 0)
  return { query: params.get('q') || '', offset: Number.isInteger(raw) && raw >= 0 && raw <= 40 && raw % SEARCH_PAGE_SIZE === 0 ? raw : 0,
    library: params.get('library') || 'LIB001', available: params.get('available') === 'true' }
}
export function changeSearchContext(params: URLSearchParams, changes: Record<string, string>) {
  const next = new URLSearchParams(params)
  Object.entries(changes).forEach(([key, value]) => next.set(key, value))
  next.delete('offset')
  return next
}
