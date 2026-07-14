import { authFetch, apiJson, ApiError } from './api'
import { withPagination, type PaginationMetadata } from './pagination'

export type ConversionJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export const TERMINAL_JOB_STATUSES: ReadonlySet<ConversionJobStatus> = new Set([
  'completed',
  'failed',
  'cancelled',
])

export interface ConversionJob {
  id: string
  user_id: string
  source_file_id: string
  output_format: string
  quality: string | null
  status: ConversionJobStatus
  progress: number | null
  error_message: string | null
  output_file_id: string | null
  converter_name: string | null
  source_filename: string | null
  source_media_type: string | null
  source_extension: string | null
  source_size_bytes: number | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  updated_at: string | null
}

export interface ConversionJobListResponse {
  jobs: ConversionJob[]
  pagination: PaginationMetadata
}

export interface ConversionJobCreatePayload {
  id: string
  output_format: string
  quality?: string | null
}

export function isTerminalJobStatus(status: ConversionJobStatus): boolean {
  return TERMINAL_JOB_STATUSES.has(status)
}

export async function listJobs(
  statusFilter?: ConversionJobStatus,
  page = 1,
  pageSize = 100,
  includeCompleted = true,
): Promise<ConversionJob[]> {
  let baseUrl = statusFilter
    ? `/api/jobs?status_filter=${encodeURIComponent(statusFilter)}`
    : '/api/jobs'
  if (!includeCompleted && !statusFilter) {
    baseUrl += '?include_completed=false'
  }
  const url = withPagination(baseUrl, page, pageSize)
  const data = await apiJson<ConversionJobListResponse>(url)
  return data.jobs
}

export async function getJob(jobId: string): Promise<ConversionJob> {
  return apiJson<ConversionJob>(`/api/jobs/${encodeURIComponent(jobId)}`)
}

export async function createJob(payload: ConversionJobCreatePayload): Promise<ConversionJob> {
  return apiJson<ConversionJob>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function cancelJob(jobId: string): Promise<ConversionJob> {
  return apiJson<ConversionJob>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  })
}

export async function retryJob(jobId: string): Promise<ConversionJob> {
  return apiJson<ConversionJob>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
  })
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await authFetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText || 'Delete failed')
  }
}

/**
 * Download the converted output file for a completed job.
 * Throws ApiError if the job is not completed or output is unavailable.
 */
export async function downloadJobOutput(job: ConversionJob): Promise<Blob> {
  if (!job.output_file_id) {
    throw new ApiError(409, 'Job has no output file')
  }
  const response = await authFetch(`/api/files/${encodeURIComponent(job.output_file_id)}`)
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText || 'Download failed')
  }
  return response.blob()
}

// ============================================================================
// Compression jobs
//
// Compression keeps the file's format and only reduces its size, so a
// compression job carries a `compression_level` preset instead of an
// `output_format`/`quality` pair. The status lifecycle is identical to
// conversion jobs.
// ============================================================================

export interface CompressionJob {
  id: string
  user_id: string
  source_file_id: string
  compression_level: string | null
  status: ConversionJobStatus
  progress: number | null
  error_message: string | null
  output_file_id: string | null
  compressor_name: string | null
  source_filename: string | null
  source_media_type: string | null
  source_extension: string | null
  source_size_bytes: number | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  updated_at: string | null
}

export interface CompressionJobListResponse {
  jobs: CompressionJob[]
  pagination: PaginationMetadata
}

export interface CompressionJobCreatePayload {
  id: string
  compression_level?: string | null
}

export async function listCompressionJobs(
  statusFilter?: ConversionJobStatus,
  page = 1,
  pageSize = 100,
  includeCompleted = true,
): Promise<CompressionJob[]> {
  let baseUrl = statusFilter
    ? `/api/compression-jobs?status_filter=${encodeURIComponent(statusFilter)}`
    : '/api/compression-jobs'
  if (!includeCompleted && !statusFilter) {
    baseUrl += '?include_completed=false'
  }
  const url = withPagination(baseUrl, page, pageSize)
  const data = await apiJson<CompressionJobListResponse>(url)
  return data.jobs
}

export async function getCompressionJob(jobId: string): Promise<CompressionJob> {
  return apiJson<CompressionJob>(`/api/compression-jobs/${encodeURIComponent(jobId)}`)
}

export async function createCompressionJob(payload: CompressionJobCreatePayload): Promise<CompressionJob> {
  return apiJson<CompressionJob>('/api/compression-jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function cancelCompressionJob(jobId: string): Promise<CompressionJob> {
  return apiJson<CompressionJob>(`/api/compression-jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  })
}

export async function retryCompressionJob(jobId: string): Promise<CompressionJob> {
  return apiJson<CompressionJob>(`/api/compression-jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
  })
}

export async function deleteCompressionJob(jobId: string): Promise<void> {
  const response = await authFetch(`/api/compression-jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText || 'Delete failed')
  }
}
