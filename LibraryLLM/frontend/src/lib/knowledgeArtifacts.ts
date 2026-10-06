import { getToken } from './api'

export type ArtifactKind = 'key-concepts' | 'summary' | 'flashcards' | 'mindmap' | 'quiz'
export interface Provenance {
  sourceChunkIds: string[]
  pageStart?: number | null
  pageEnd?: number | null
  chapter?: string | null
  section?: string | null
}
export interface Concept extends Provenance { id: string; label: string }
export interface Card extends Provenance { id: string; type: 'definition' | 'cloze'; front: string; back: string; sourceExcerpt: string }
export type QuizQuestionType = 'mcq' | 'fill_blank' | 'matching'
export interface QuizOptions { questionTypes: QuizQuestionType[]; questionCount: number }
interface QuestionBase extends Provenance { id: string; question: string; sourceExcerpt: string }
export interface TextQuestion extends QuestionBase { type: 'fill_blank' | 'true_false'; correctAnswer: string }
export interface MCQQuestion extends QuestionBase { type: 'mcq'; options: string[]; correctAnswer: string }
export interface MatchingItem extends Provenance { id: string; text: string; sourceExcerpt: string }
export interface MatchingQuestion extends QuestionBase { type: 'matching'; leftItems: MatchingItem[]; rightItems: { id: string; text: string }[]; correctMatches: Record<string, string> }
export type Question = TextQuestion | MCQQuestion | MatchingQuestion
export interface MapNode extends Concept { type: string }
export interface Artifact {
  id: string; type: string; documentId: string; generatorVersion?: string
  options: { mode?: string; questionTypes?: QuizQuestionType[]; questionCount?: number }
  content: {
    concepts?: Concept[]; sentences?: (Provenance & { text: string })[]; cards?: Card[]
    nodes?: MapNode[]; edges?: { source: string; target: string; relation: string }[]; questions?: Question[]
    generatedCounts?: Partial<Record<QuizQuestionType, number>>; requestedCount?: number; messages?: string[]
  }
  analysis?: { sampled: boolean }
}
export interface Source extends Provenance { chunkId: string; filename: string; text: string }

async function request<T>(documentId: string, path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  if (!token) throw new Error('Sign in to use Knowledge Tools.')
  const response = await fetch(`/rag-api/rag/documents/${encodeURIComponent(documentId)}/${path}`, {
    ...options, cache: 'no-store', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (getToken() !== token) throw new Error('The signed-in account changed. Open the document again.')
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: 'Sign in again to use Knowledge Tools.', 403: 'You do not have access to this document.',
      404: 'This document or artifact is no longer available in this session.',
      409: 'Document text is unavailable. Restore or upload the PDF again.',
      413: 'This document is too large for Knowledge Tools.',
    }
    throw new Error(messages[response.status] || 'Knowledge Tools could not complete this request. Please try again.')
  }
  return response.json()
}
export const listArtifacts = (id: string, signal?: AbortSignal) => request<{ artifacts: Artifact[] }>(id, 'artifacts', { signal })
export const generateArtifact = (id: string, kind: ArtifactKind, mode: string, signal?: AbortSignal, quizOptions?: QuizOptions) =>
  request<{ artifact: Artifact; cached: boolean }>(id, `artifacts/${kind}`, { method: 'POST', body: JSON.stringify({ scope: 'document', mode, ...(kind === 'quiz' ? quizOptions : {}) }), signal })
export const getSource = (id: string, chunk: string, signal?: AbortSignal) => request<Source>(id, `sources/${encodeURIComponent(chunk)}`, { signal })
