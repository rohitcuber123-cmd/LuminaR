import { coreRequest, returnBook } from "../lib/api";

export interface Inventory {
  library_id: string;
  work_id: string;
  isbn?: string;
  total_copies: number;
  available_copies: number;
  shelf_location?: string;
  title?: string;
  authors?: string;
}
export interface RecordItem {
  [key: string]: unknown;
  user_id: number;
  work_id: string;
  title?: string;
  status: string;
  issue_id?: number;
  reservation_id?: number;
  fine_id?: number;
  activity_id?: number;
  issued_at?: string;
  due_date?: string;
  reserved_at?: string;
  created_at?: string;
  amount?: number;
  activity_type?: string;
  description?: string;
  returned_at?: string | null;
  exists?: boolean;
  borrowed?: boolean;
  readable?: boolean;
  rag_available?: boolean;
  can_read?: boolean;
  can_know_more?: boolean;
}
export interface PreviewRow {
  row_number?: number;
  isbn?: string;
  work_id?: string;
  catalogue_title?: string;
  title?: string;
  total_copies?: number;
  available_copies?: number;
  status: string;
  reason?: string;
  candidates?: unknown[];
}
export interface ImportPreview {
  preview_id: string;
  library_id: string;
  filename: string;
  summary: Record<string, number>;
  rows: PreviewRow[];
}
export interface ImportResult {
  imported: number;
  consolidated: number;
  skipped_existing: number;
  skipped_not_found: number;
  skipped_ambiguous: number;
  skipped_invalid: number;
  failed: number;
  errors: { work_id: string; error: string }[];
}
export const api = coreRequest;
export const segment = encodeURIComponent;
export const getIssues = () => api<{ issues: RecordItem[] }>("/issues/all");
export const getReservations = () =>
  api<{ reservations: RecordItem[] }>("/reservations/all");
export const getFines = () =>
  api<{ fines: RecordItem[]; total_unpaid: number }>("/fines/all");
export const getActivity = () =>
  api<{ activities: RecordItem[] }>("/activity/all");
export async function getInventory(library: string, signal?: AbortSignal) {
  const items: Inventory[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await api<{ results: Inventory[] }>(
      `/inventory/?library_id=${segment(library)}&limit=100&offset=${offset}`,
      { signal },
    );
    items.push(...page.results);
    if (page.results.length < 100) return items;
  }
}
export function previewImport(library: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  // FastAPI declares library_id as a query parameter on preview.
  return api<ImportPreview>(
    `/inventory/import/preview?library_id=${segment(library)}`,
    { method: "POST", body },
  );
}
export function confirmImport(preview: ImportPreview) {
  const body = new FormData();
  body.append("preview_id", preview.preview_id);
  body.append("library_id", preview.library_id);
  return api<ImportResult>("/inventory/import/confirm", {
    method: "POST",
    body,
  });
}
export function mutate(path: string, method = "POST", data?: unknown) {
  if (method === "POST" && path.startsWith("/issues/return/")) {
    return returnBook(path.slice("/issues/return/".length));
  }
  return api(path, {
    method,
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
}
export const activeReservation = (row: RecordItem) =>
  ["ACTIVE", "READY_FOR_PICKUP"].includes(row.status);
export function dateValue(value?: string) {
  if (!value) return NaN;
  return Date.parse(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`);
}
export const overdue = (row: RecordItem) =>
  row.status === "ISSUED" && dateValue(row.due_date) < Date.now();
