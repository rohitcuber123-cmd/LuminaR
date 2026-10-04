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
  readable?: boolean
  rag_available?: boolean
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
  readable?: boolean
  rag_available?: boolean
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

export interface RankedPageMetadata {
  offset?: number
  limit?: number
  returned?: number
  has_more?: boolean
  next_offset?: number | null
  total_ranked_candidates?: number
}

export interface SearchResponse extends RankedPageMetadata {
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

export interface RecommendationsResponse extends RankedPageMetadata {
  recommendation_mode?: string
  seed_work_ids?: string[]
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

export interface KnowMoreBook extends RAGBook {
  readable: boolean
  rag_available: boolean
  borrowed: boolean
}

export interface KnowMoreBooksResponse {
  count: number
  books: KnowMoreBook[]
}

export interface ReadableBook extends RAGBook {
  text: string
}

export const BORROW_STATE_CHANGED = 'luminar-borrow-state-changed'

export function notifyBorrowChanged() {
  window.dispatchEvent(new Event(BORROW_STATE_CHANGED))
  localStorage.setItem(BORROW_STATE_CHANGED, String(Date.now()))
}

export function getKnowMoreBooks() {
  return request<KnowMoreBooksResponse>(`${CORE_API}/know-more/books`, { cache: 'no-store' })
}

export function getReadableBook(workId: string) {
  return request<ReadableBook>(`${CORE_API}/books/${encodeURIComponent(workId)}/read`)
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

export class ApiError extends Error {
  status: number
  code?: string
  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();

  const headers = new Headers(options.headers);

  if (
    options.body &&
    !headers.has("Content-Type") &&
    !(options.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new Error(
      "Unable to reach the requested service. Check the backend connection and try again.",
    );
  }

  // ==========================================================
  // AUTH FAILURE
  // ==========================================================

  if (
    response.status === 401 &&
    !url.endsWith("/auth/login") && !url.endsWith("/auth/staff-login") &&
    token === getToken()
  ) {
    localStorage.removeItem("luminar_token");

    localStorage.removeItem("luminar_user");

    window.dispatchEvent(new Event("luminar-session-expired"));
    throw new Error("Your session has expired. Please log in again.");
  }

  // ==========================================================
  // GENERAL ERROR
  // ==========================================================

  if (!response.ok) {
    const messages: Record<number, string> = {
      401: "Please check your email and password, then try again.",
      403: "Your account does not have permission for this action.",
      404: "This record could not be found. Refresh the page and try again.",
      422: "Please check the entered values and try again.",
    };
    let message = messages[response.status] || "The request could not be completed. Please try again.";

    let errorCode: string | undefined;
    try {
      const error = await response.json();

      if (response.status >= 500) {
        message = "The server could not complete this request. Please try again shortly.";
      } else if (typeof error.detail === "string") {
        message = error.detail;
      } else if (typeof error.detail?.message === 'string') {
        message = error.detail.message;
        errorCode = typeof error.detail.code === 'string' ? error.detail.code : undefined;
      } else if (Array.isArray(error.detail)) {
        const details = error.detail.flatMap((item: { loc?: unknown[]; msg?: string }) => {
          if (typeof item?.msg !== "string") return [];
          const field = Array.isArray(item.loc)
            ? item.loc.filter((part) => !["body", "query", "path"].includes(String(part))).join(" / ").replaceAll("_", " ")
            : "";
          return [field ? `${field}: ${item.msg}` : item.msg];
        });
        if (details.length) message = details.join("; ");
      }
    } catch {
      // Keep default error
    }

    throw new ApiError(message, response.status, errorCode);
  }

  // ==========================================================
  // EMPTY RESPONSE
  // ==========================================================

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
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
  saveHistory = true,
  offset = 0
) {

  const response = await request<SearchResponse>(
    `${SEARCH_API}/search`,
    {
      method: 'POST',

      body: JSON.stringify({
        query,
        limit: topK,
        offset,
        library_id: libraryId,
        available_at_library:
          availableAtLibrary,
        save_history: saveHistory,
      }),
    }
  )
  const workIds = response.results.flatMap(result => result.work_id ? [result.work_id] : [])
  if (!workIds.length) return response
  const capabilities = await request<{ books: Array<{ work_id: string; readable: boolean; rag_available: boolean }> }>(
    `${CORE_API}/books/capabilities`,
    { method: 'POST', body: JSON.stringify({ work_ids: workIds }) },
  ).catch(() => ({ books: [] }))
  const byId = new Map(capabilities.books.map(book => [book.work_id, book]))
  return { ...response, results: response.results.map(result => ({ ...result, ...byId.get(result.work_id || '') })) }
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
  limit = 10,
  offset = 0
): Promise<RecommendationsResponse> {

  return request<RecommendationsResponse>(
    `${RECOMMENDATION_API}/recommendations?limit=${limit}&offset=${offset}`
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

  const result = await request(
    `${CORE_API}/issues/issue`,
    {
      method: 'POST',

      body: JSON.stringify({
        work_id: workId,
      }),
    }
  )
  notifyBorrowChanged()
  return result
}


export async function returnBook(
  issueId: number | string
) {

  const result = await request(
    `${CORE_API}/issues/return/${issueId}`,
    {
      method: 'POST',
    }
  )
  notifyBorrowChanged()
  return result
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
  documentId?: string | null,
  bookMode = false,
) {

  const body: Record<string, any> = {
    query,
    depth,
  }

  if (documentId) {
    if (bookMode) body.work_id = documentId
    else body.document_id = documentId
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

export function coreRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  return request<T>(`${CORE_API}${path}`, options)
}

export function staffLogin(email: string, password: string): Promise<LoginResponse> {
  return coreRequest<LoginResponse>('/auth/staff-login', {
    method: 'POST', body: JSON.stringify({ email, password }),
  })
}
