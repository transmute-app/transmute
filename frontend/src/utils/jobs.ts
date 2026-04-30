import { authFetch, apiJson, ApiError } from './api'

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
}

export interface ConversionJobCreatePayload {
  id: string
  output_format: string
  quality?: string | null
}

export function isTerminalJobStatus(status: ConversionJobStatus): boolean {
  return TERMINAL_JOB_STATUSES.has(status)
}

export async function listJobs(statusFilter?: ConversionJobStatus): Promise<ConversionJob[]> {
  const url = statusFilter
    ? `/api/jobs?status_filter=${encodeURIComponent(statusFilter)}`
    : '/api/jobs'
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
