export interface Rules {
  trim_width_mm: number | null; trim_height_mm: number | null;
  tolerance_mm: number; bleed_mm: number; min_dpi: number;
  min_pages: number; max_pages: number; require_embedded_fonts: boolean;
  require_explicit_trim: boolean; flag_rgb: boolean;
}
export interface Profile {
  id: string; name: string; version: number; family_id: string;
  rules: Rules; digest: string; created_at: number;
}
export interface User { id: string; email: string; role: 'owner' | 'operator' | 'viewer'; active: boolean; created_at: number }
export interface Me {
  user: User; workspace: {id: string; name: string; plan: string; retention_days: number};
  csrf_token: string; capabilities: {professional_preflight: boolean; automatic_fixes: boolean;
    automatic_print_release: boolean; assistant_mode: string; max_upload_mb: number; version: string};
}
export interface Finding {code: string; severity: 'error' | 'warning' | 'info'; message: string; page: number | null; evidence: Record<string, unknown>}
export interface Summary {pages: number; errors: number; warnings: number; info: number; image_placements: number; fonts: number; color_spaces: string[]}
export interface Report {
  schema_version: number; engine?: {name: string; version: string; pypdf_version: string};
  file_sha256: string; profile_digest?: string; status: string; print_ready: false; release_allowed: false;
  summary?: Summary; findings?: Finding[]; coverage?: Record<string, string>;
  pages?: {page: number; width_mm: number; height_mm: number; rotation: number; user_unit: number; explicit_trim_box: boolean; bleed_margins_mm: number[]}[];
  fonts?: {page: number; name: string; subtype: string; embedded_program_present: boolean}[];
  images?: {page: number; width_px: number; height_px: number; effective_dpi: number; color_space: string}[];
  error_code?: string;
}
export interface Job {
  id: string; filename: string; order_ref: string; size_bytes: number; sha256: string;
  profile_id: string; profile_name: string; profile_version: number;
  status: 'queued' | 'processing' | 'review' | 'blocked' | 'error';
  decision: 'accepted' | 'rejected' | null; created_at: number; completed_at: number | null;
  summary: Summary | null; error_code: string | null; preview_available: boolean; attempts: number;
  report?: Report | null; profile_snapshot?: Rules; profile_digest?: string;
  report_digest?: string | null; decision_note?: string; reviewer_id?: string; reviewed_at?: number;
}
export interface Page<T> {items: T[]; total: number; offset: number; limit: number}
export interface Stats {
  total: number; by_status: Record<string, number>; accepted: number; pending_review: number;
  daily: {date: string; count: number}[]; worker_online: boolean;
  usage: {month: string; uploads: number; monthly_limit: number; storage_bytes: number; storage_limit_bytes: number};
}
export interface Audit {id: string; action: string; actor_id: string | null; job_id: string | null; details: Record<string, unknown>; created_at: number}
export interface Key {id: string; name: string; prefix: string; scope: string; expires_at: number; revoked_at: number | null}
export interface Assistant {mode: string; text: string; warning: string | null; requires_human_review: boolean; changes_verdict: false}
