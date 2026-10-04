// ============================================================
// LUMINAR API CLIENT
// ============================================================

const CORE_API = '/api'
const SEARCH_API = '/search-api'
const RECOMMENDATION_API = '/recommendation-api'
const RAG_API = '/rag-api'


// ============================================================
// TYPES
// ============================================================

export interface LoginResponse {
  access_token: string
  token_type?: string
  user?: any
}

export interface BackendBook {
  book_id: number
  work_id: string
  title: string
  authors: string
  subjects: string
  description: string | null
  average_rating: number
  rating_count: number
  reading_log_count: number
  shelf_location: string | null
  total_copies: number
  available_copies: number
  created_at: string
}

export interface BooksResponse {
  count: number
  results: BackendBook[]
}

export interface CategoryPreviewBook {
  work_id: string
  title: string
  authors: string | null
  book_id: number
}

export interface Category {
  name: string
  count: number
  preview_book: CategoryPreviewBook
}

export interface CategoriesResponse {
  count: number
  categories: Category[]
}

export interface SearchResult {
  work_id?: string
  title?: string | null
  authors?: string | null
  subjects?: string | null

  rating?: number | null
  rating_count?: number | null
  read_logs?: number | null

  hnsw_score?: number
  rerank_score?: number

  library_id?: string | null
  library_available?: boolean

  physical_copies?: number
  available_physical_copies?: number
  
  shelf_location?: string | null
  isbn?: string | null
  rank?: number
}

export interface SearchResponse {
  system?: string
  query?: string

  results: SearchResult[]

  timing_ms?: any
}

export interface RecommendationScoreBreakdown {
  score: number
  semantic_score: number
  subject_score: number
  author_score: number
  borrowing_score: number
  reservation_score: number
  rating_score: number
  popularity_score: number
  availability_score: number
  feedback_score: number
}

export interface Recommendation {
  work_id: string
  book_id: number | null
  title: string
  authors: string | null
  subjects: string | null
  average_rating: number
  total_copies: number
  available_copies: number
  shelf_location: string | null
  library_available: boolean
  score: number
  score_breakdown: RecommendationScoreBreakdown
}

export interface RecommendationsResponse {
  user_id: number
  count: number
  recommendations: Recommendation[]
}

export interface RAGDocument {
  document_id: string
  filename: string

  chunks: number
  pages: number
}

export interface RAGDocumentsResponse {
  count: number
  documents: RAGDocument[]
}

export interface RAGBook {
  work_id: string
  title: string
  authors: string[]
}

export interface RAGBooksResponse {
  count: number
  books: RAGBook[]
}

export interface RAGResponse {
  question: string

  depth: string

  answer: string

  verdict?: string

  fast_filter_decision?: string

  sources: Array<{
    filename: string
    page: number
    chunk_id?: string
    rerank_score?: number
    chapter?: string
    title?: string
    author?: string
  }>

  retrieval?: {
    candidate_count?: number
    context_count?: number
    context_characters?: number
  }

  timing_ms?: {
    retrieval?: number
    generation?: number
    total?: number
  }
}


// ============================================================
// TOKEN
// ============================================================

export function getToken(): string | null {
  return localStorage.getItem('luminar_token')
}


// ============================================================
// GENERIC REQUEST
// ============================================================

async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {

  const token = getToken()

  const headers = new Headers(
    options.headers
  )

  if (
    options.body &&
    !headers.has('Content-Type') &&
    !(options.body instanceof FormData)
  ) {

    headers.set(
      'Content-Type',
      'application/json'
    )
  }

  if (token) {

    headers.set(
      'Authorization',
      `Bearer ${token}`
    )
  }

  const response = await fetch(
    url,
    {
      ...options,
      headers,
    }
  )


  // ==========================================================
  // AUTH FAILURE
  // ==========================================================

  if (response.status === 401) {

    localStorage.removeItem(
      'luminar_token'
    )

    localStorage.removeItem(
      'luminar_user'
    )

    throw new Error(
      'Your session has expired. Please log in again.'
    )
  }


  // ==========================================================
  // GENERAL ERROR
  // ==========================================================

  if (!response.ok) {

    let message =
      `Request failed with status ${response.status}`

    try {

      const error =
        await response.json()

      if (typeof error.detail === 'string') {

        message = error.detail

      } else if (error.detail) {

        message =
          JSON.stringify(error.detail)
      }

    } catch {
      // Keep default error
    }

    throw new Error(message)
  }


  // ==========================================================
  // EMPTY RESPONSE
  // ==========================================================

  if (response.status === 204) {

    return undefined as T
  }


  return response.json()
}


// ============================================================
// AUTH
// ============================================================

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {

  return request<LoginResponse>(
    `${CORE_API}/auth/login`,
    {
      method: 'POST',

      body: JSON.stringify({
        email,
        password,
      }),
    }
  )
}


export async function register(
  data: Record<string, any>
) {

  return request(
    `${CORE_API}/auth/register`,
    {
      method: 'POST',

      body: JSON.stringify(data),
    }
  )
}


export async function verifyOTP(
  email: string,
  otp: string
) {

  return request(
    `${CORE_API}/auth/verify-email`,
    {
      method: 'POST',

      body: JSON.stringify({
        email,
        otp,
      }),
    }
  )
}


export async function resendOTP(
  email: string
) {

  return request(
    `${CORE_API}/auth/resend-verification`,
    {
      method: 'POST',

      body: JSON.stringify({
        email,
      }),
    }
  )
}


// ============================================================
// BOOKS
// ============================================================

export async function getBooks(
  limit = 20,
  offset = 0
): Promise<BooksResponse> {

  return request<BooksResponse>(
    `${CORE_API}/books/?limit=${limit}&offset=${offset}`
  )
}


// ============================================================
// CATEGORIES
// ============================================================

export async function getCategories(): Promise<CategoriesResponse> {

  return request<CategoriesResponse>(
    `${CORE_API}/books/categories`
  )
}


// ============================================================
// SINGLE BOOK
// ============================================================

export async function getBook(
  workId: string
): Promise<BackendBook> {

  return request<BackendBook>(
    `${CORE_API}/books/${encodeURIComponent(workId)}`
  )
}


// ============================================================
// POPULAR BOOKS
// ============================================================

export async function getPopularBooks(
  limit = 10
): Promise<BackendBook[]> {

  const response = await request<BooksResponse>(
    `${CORE_API}/books/popular?limit=${limit}`
  )

  return response.results
}


// ============================================================
// NEW ARRIVALS
// ============================================================

export async function getNewArrivals(
  limit = 10
): Promise<BackendBook[]> {

  const response = await request<BooksResponse>(
    `${CORE_API}/books/new-arrivals?limit=${limit}`
  )

  return response.results
}


// ============================================================
// SEARCH
// ============================================================

export async function searchBooks(
  query: string,
  topK = 10,
  libraryId = 'LIB001',
  availableAtLibrary = true,
  saveHistory = true
) {

  return request<SearchResponse>(
    `${SEARCH_API}/search`,
    {
      method: 'POST',

      body: JSON.stringify({
        query,
        top_k: topK,
        library_id: libraryId,
        available_at_library:
          availableAtLibrary,
        save_history: saveHistory,
      }),
    }
  )
}


export async function getSearchHistory(
  limit = 50
) {

  return request(
    `${SEARCH_API}/search-history?limit=${limit}`
  )
}


// ============================================================
// RECOMMENDATIONS
// ============================================================

export async function getRecommendations(
  limit = 10
): Promise<RecommendationsResponse> {

  return request<RecommendationsResponse>(
    `${RECOMMENDATION_API}/recommendations?limit=${limit}`
  )
}


export async function sendRecommendationFeedback(
  workId: string,
  feedbackType: string
) {

  return request(
    `${RECOMMENDATION_API}/feedback`,
    {
      method: 'POST',

      body: JSON.stringify({
        work_id: workId,
        feedback_type: feedbackType,
      }),
    }
  )
}


// ============================================================
// ISSUES
// ============================================================

export async function getMyIssues() {

  return request(
    `${CORE_API}/issues/my`
  )
}


export async function issueBook(
  workId: string
) {

  return request(
    `${CORE_API}/issues/issue`,
    {
      method: 'POST',

      body: JSON.stringify({
        work_id: workId,
      }),
    }
  )
}


export async function returnBook(
  issueId: number | string
) {

  return request(
    `${CORE_API}/issues/return/${issueId}`,
    {
      method: 'POST',
    }
  )
}


// ============================================================
// RESERVATIONS
// ============================================================

export async function getMyReservations() {

  return request(
    `${CORE_API}/reservations/my`
  )
}


export async function reserveBook(
  workId: string
) {

  return request(
    `${CORE_API}/reservations/`,
    {
      method: 'POST',

      body: JSON.stringify({
        work_id: workId,
      }),
    }
  )
}


export async function cancelReservation(
  reservationId: number | string
) {

  return request(
    `${CORE_API}/reservations/cancel/${reservationId}`,
    {
      method: 'POST',
    }
  )
}


// ============================================================
// FINES
// ============================================================

export async function getMyFines() {

  return request<any>(
    `${CORE_API}/fines/my`
  )
}


export async function payFine(
  fineId: number | string
) {

  return request(
    `${CORE_API}/fines/pay/${fineId}`,
    {
      method: 'POST',
    }
  )
}


// ============================================================
// ACTIVITY
// ============================================================

export async function getMyActivity() {
  return request<any>(
    `${CORE_API}/activity/my`
  )
}


// ============================================================
// READING LIST
// ============================================================

export async function getReadingList() {
  return request<{ count: number; items: any[] }>(
    `${CORE_API}/reading-list/my`
  )
}

export async function addToReadingList(workId: string) {
  return request(
    `${CORE_API}/reading-list/`,
    {
      method: 'POST',
      body: JSON.stringify({
        work_id: workId,
      }),
    }
  )
}

export async function removeFromReadingList(workId: string) {
  return request(
    `${CORE_API}/reading-list/${workId}`,
    {
      method: 'DELETE',
    }
  )
}


// ============================================================
// RAG
// ============================================================

export async function getRAGDocuments() {

  return request<RAGDocumentsResponse>(
    `${RAG_API}/rag/documents`
  )
}


export async function getRAGBooks() {

  return request<RAGBooksResponse>(
    `${RAG_API}/rag/books`
  )
}


export async function uploadRAGDocument(
  file: File
) {

  const formData = new FormData()

  formData.append(
    'file',
    file
  )

  return request(
    `${RAG_API}/rag/upload`,
    {
      method: 'POST',
      body: formData,
    }
  )
}


export async function askRAG(
  query: string,
  depth:
    | 'concise'
    | 'normal'
    | 'detailed'
    | 'comprehensive',
  documentId?: string | null
) {

  const body: Record<string, any> = {
    query,
    depth,
  }

  if (documentId) {
    body.document_id = documentId
  }

  return request<RAGResponse>(
    `${RAG_API}/rag/ask`,
    {
      method: 'POST',

      body: JSON.stringify(body),
    }
  )
}


// ============================================================
// HEALTH
// ============================================================

export async function getCoreHealth() {

  return request(
    `${CORE_API}/health`
  )
}


export async function getSearchHealth() {

  return request(
    `${SEARCH_API}/health`
  )
}


export async function getRAGHealth() {

  return request(
    `${RAG_API}/health`
  )
}