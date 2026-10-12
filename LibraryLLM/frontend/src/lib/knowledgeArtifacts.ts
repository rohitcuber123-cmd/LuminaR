import { ApiError, getToken } from './api'
import { assetBase, type LibraryAssetTarget } from './libraryAssets'

export type ArtifactKind = 'key-concepts' | 'summary' | 'flashcards' | 'mindmap' | 'quiz'
export interface Provenance {
  sourceChunkIds: string[]
  pageStart?: number | null
  pageEnd?: number | null
  chapter?: string | null
  section?: string | null
  sources?: { chunkId: string; page?: number | null }[]
}
export interface Concept extends Provenance { id: string; label: string; explanation?: string; confidence?: number }
export interface Card extends Provenance { id: string; type: 'definition' | 'cloze' | 'concept' | 'relationship' | 'process' | 'application' | 'comparison'; front: string; back: string; sourceExcerpt: string }
export type QuizQuestionType = 'mcq' | 'fill_blank' | 'matching'
export interface QuizOptions { questionTypes: QuizQuestionType[]; questionCount: number }
interface QuestionBase extends Provenance { id: string; question: string; sourceExcerpt: string }
export interface TextQuestion extends QuestionBase { type: 'fill_blank' | 'true_false'; correctAnswer: string }
export interface ClozeGrade {
  verdict: 'CORRECT' | 'PARTIAL' | 'INCORRECT'; canonical_answer: string; feedback: string
  source_pages: number[]; source_chunk_ids: string[]
}
// Option text is the stable identity; the backend guarantees unique strings.
// Neither the API adapter nor Quiz reshuffles or converts it to a numeric key.
export interface MCQQuestion extends QuestionBase { type: 'mcq'; options: string[]; correctAnswer: string; explanation?: string }
export interface MatchingItem extends Provenance { id: string; text: string; sourceExcerpt: string }
export interface MatchingQuestion extends QuestionBase { type: 'matching'; leftItems: MatchingItem[]; rightItems: { id: string; text: string }[]; correctMatches: Record<string, string> }
export type Question = TextQuestion | MCQQuestion | MatchingQuestion
export interface MapNode extends Concept { type: string }
export interface Artifact {
  id: string; type: string; documentId: string; generatorVersion?: string
  options: { mode?: string; questionTypes?: QuizQuestionType[]; questionCount?: number }
  content: {
    concepts?: Concept[]; sentences?: (Provenance & { text: string })[]; cards?: Card[]
    sections?: { title: string; sentences: (Provenance & { text: string })[] }[]
    nodes?: MapNode[]; edges?: { source: string; target: string; relation: string }[]; questions?: Question[]
    generatedCounts?: Partial<Record<QuizQuestionType, number>>; requestedCount?: number; messages?: string[]
    learningItemCount?: number; matchingAllocation?: { sets: number; pairs: number; requestedPairs: number }
  }
  analysis?: { sampled: boolean }
}
export interface Source extends Provenance { chunkId: string; filename: string; text: string }

async function request<T>(documentId: string, path: string, options: RequestInit = {}, libraryAsset?: LibraryAssetTarget): Promise<T> {
  const token = getToken()
  if (!token) throw new Error('Sign in to use Knowledge Tools.')
  const source = libraryAsset ? `/rag-api${assetBase(libraryAsset.libraryId, libraryAsset.assetId)}` : `/rag-api/rag/documents/${encodeURIComponent(documentId)}`
  const response = await fetch(`${source}/${path}`, {
    ...options, cache: 'no-store', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (getToken() !== token) throw new Error('The signed-in account changed. Open the document again.')
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: 'Sign in again to use Knowledge Tools.', 403: 'You do not have access to this document.',
      404: libraryAsset ? 'This library document or study artifact is no longer available.' : 'This document or artifact is no longer available in this session.',
      409: libraryAsset ? 'Document text is unavailable. Ask library staff to reprocess this document.' : 'Document text is unavailable. Restore or upload the PDF again.',
      413: 'This document is too large for Knowledge Tools.',
      429: 'A study artifact is already being prepared. Please wait, then retry.',
    }
    throw new ApiError(messages[response.status] || 'Knowledge Tools could not complete this request. Please try again.', response.status)
  }
  return response.json()
}
export const listArtifacts = (id: string, signal?: AbortSignal, libraryAsset?: LibraryAssetTarget) => request<{ artifacts: Artifact[] }>(id, 'artifacts', { signal }, libraryAsset)
export const generateArtifact = (id: string, kind: ArtifactKind, mode: string, signal?: AbortSignal, quizOptions?: QuizOptions, libraryAsset?: LibraryAssetTarget) =>
  request<{ artifact: Artifact; cached: boolean }>(id, `artifacts/${kind}`, { method: 'POST', body: JSON.stringify({ scope: 'document', mode, ...(kind === 'quiz' ? quizOptions : {}) }), signal }, libraryAsset)
export const getSource = (id: string, chunk: string, signal?: AbortSignal, libraryAsset?: LibraryAssetTarget) => request<Source>(id, `sources/${encodeURIComponent(chunk)}`, { signal }, libraryAsset)
export const gradeCloze = async (documentId: string, quizId: string, itemId: string, answer: string, signal?: AbortSignal, libraryAsset?: LibraryAssetTarget) => {
  const result = await request<ClozeGrade>(documentId, `artifacts/${encodeURIComponent(quizId)}/cloze/${encodeURIComponent(itemId)}/grade`, {
    method: 'POST', body: JSON.stringify({ answer }), signal,
  }, libraryAsset)
  if (!['CORRECT', 'PARTIAL', 'INCORRECT'].includes(result.verdict) || typeof result.canonical_answer !== 'string' || typeof result.feedback !== 'string') {
    throw new Error('Answer checking returned an incomplete result. Keep your answer and retry.')
  }
  return result
}
