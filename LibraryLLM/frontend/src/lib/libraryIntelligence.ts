import { institutionApi } from './institutions'

export type IntelligenceJob = {
  job_id: string; library_id: string; target: 'SEARCH_INDEX' | 'KNOWLEDGE_GRAPH';
  state: string; stage: string; progress_current: number; progress_total: number;
  created_at: string; started_at: string | null; completed_at: string | null;
  error_code: string | null; error_message: string | null;
}
export type IntelligenceTarget = {
  target: IntelligenceJob['target']; status: string; active_status: string;
  active_generation_id: string | null; source_generation_id: string | null;
  generation_sequence: number | null; record_count: number; built_at: string | null;
  last_build_duration_seconds: number | null; node_count: number | null; edge_count: number | null;
  artifact_verified: boolean; current_job: IntelligenceJob | null; latest_job: IntelligenceJob | null;
  can_retry: boolean; model: string; dimension: number;
  parameters: { M: number; efConstruction: number; efSearch: number };
}
export type IntelligenceStatus = {
  library_id: string; can_build: boolean; eligible_book_count: number;
  dataset: { generation_id: string | null; sequence: number | null };
  search: IntelligenceTarget; kg: IntelligenceTarget;
}
export const activeBuild = (target: IntelligenceTarget) => !!target.current_job && ['QUEUED','RUNNING','VALIDATING','PUBLISHING'].includes(target.current_job.state)
export const intelligenceStatus = (id: string, signal?: AbortSignal) => institutionApi<IntelligenceStatus>(`/libraries/${id}/intelligence`, 'GET', undefined, signal)
export const requestIntelligenceBuild = (id: string, target: IntelligenceJob['target'], signal?: AbortSignal) => institutionApi<IntelligenceJob>(`/libraries/${id}/intelligence/builds`, 'POST', { target }, signal)
