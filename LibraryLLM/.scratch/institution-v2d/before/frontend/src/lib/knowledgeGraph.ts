import { request } from './api'
export interface KGBook { work_id: string; title: string; authors: string[]; subjects: string[] }
export interface ReasonPath { nodes: string[]; kind: string; label: string; contribution: number; catalogue_degree: number; relation_weight?: number; importance?: number; feature_weight?: number; provenance: { work_id: string; field: string; value: string; description_sha256?: string; extractor?: string }[] }
export interface KGRecommendation extends KGBook { score: number; reason_paths: ReasonPath[] }
export interface KGNode { id: string; kind: string; label: string; seed: boolean }
export interface KGEdge { source: string; target: string; predicate: string }
export interface GraphMeta { books: number; edges: number; features: Record<string, number>; isolated_books: number; missing_authors: number; missing_subjects: number; created_at: string; catalogue_hash: string }
export interface Diversity { subject_pairwise_distance: number | null; result_count: number; unique_authors: number; unique_subjects: number }
export interface KGMetrics { overlap_at_k: number; jaccard: number; intersection_count: number; kg_only_ids: string[]; existing_only_ids: string[]; existing_diversity: Diversity; kg_diversity: Diversity }
export interface KGResponse { seed: KGBook; recommendations: KGRecommendation[]; candidate_count: number; reason: string; exploration: { nodes: KGNode[]; edges: KGEdge[]; reason_paths_per_book_shown: number }; snapshot: GraphMeta; existing?: KGBook[]; metrics?: KGMetrics }
const base = '/api/experimental/kg'
export const graphMeta = (signal?: AbortSignal) => request<GraphMeta>(`${base}/meta`, { signal })
export const graphBooks = (q: string, signal?: AbortSignal) => request<{ books: KGBook[] }>(`${base}/books?q=${encodeURIComponent(q)}&limit=20`, { signal })
export const graphRecommend = (workId: string, compare = false, signal?: AbortSignal) => request<KGResponse>(`${base}/${compare ? 'compare' : 'more-like-this'}`, { method: 'POST', body: JSON.stringify({ work_id: workId, limit: 10 }), signal })

export interface RelatedBook extends KGRecommendation {
  book_id: number | null; average_rating: number | null; rating_count: number | null
  available_copies: number; total_copies: number; shelf_location: string | null
  availability_source: 'physical' | 'catalogue'
}
export interface RelatedBooksResponse {
  seed_work_id: string; seed: KGBook; graph_version: string; candidate_count: number
  recommendations: RelatedBook[]; limit: number; has_more: boolean; snapshot_at: string
}
export const relatedBooks = (workId: string, signal?: AbortSignal) => request<RelatedBooksResponse>(
  `/api/kg/books/${encodeURIComponent(workId)}/more-like-this?limit=10`, { signal })
