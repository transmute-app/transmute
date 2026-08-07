/**
 * Download utilities for handling blob downloads
 */

import { authFetch as fetch } from './api'

/**
 * Extract filename from content-disposition header or fallback to default
 */
function extractFilename(response: Response, fallback: string): string {
  const contentDisposition = response.headers.get('content-disposition')
  if (contentDisposition) {
    const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (match) {
      return match[1].replace(/['"]/g, '')
    }
  }
  return fallback
}

/**
 * Download a file from fetch response
 * @param response - The fetch Response object
 * @param fallbackFilename - Fallback filename if not provided in headers
 * @returns The downloaded filename
 */
export async function downloadFromResponse(response: Response, fallbackFilename: string = 'download'): Promise<string> {
  if (!response.ok) {
    throw new Error(`Download failed: ${response.statusText}`)
  }
  
  const blob = await response.blob()
  const filename = extractFilename(response, fallbackFilename)
  
  downloadBlob(blob, filename)
  
  return filename
}

/**
 * Trigger a browser download from a blob
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

/**
 * Download a file using HTTP Range requests, splitting the transfer into chunks
 * @param url - The API URL to download from (e.g. `/api/files/{id}`)
 * @param filename - The filename to save as
 * @param chunkSize - Maximum bytes per range request
 */
export async function downloadChunked(
  url: string,
  filename: string,
  chunkSize: number,
): Promise<void> {
  const headResp = await fetch(url, { method: 'HEAD' })
  if (!headResp.ok) throw new Error(`Download failed: ${headResp.statusText}`)

  const contentLength = headResp.headers.get('content-length')
  const totalBytes = contentLength ? parseInt(contentLength, 10) : 0
  const dispositionFilename = extractFilename(headResp, filename)

  if (totalBytes === 0 || totalBytes <= chunkSize) {
    const resp = await fetch(url)
    await downloadFromResponse(resp, dispositionFilename)
    return
  }

  const chunks: Blob[] = []
  let downloaded = 0

  while (downloaded < totalBytes) {
    const end = Math.min(downloaded + chunkSize - 1, totalBytes - 1)
    const resp = await fetch(url, {
      headers: { Range: `bytes=${downloaded}-${end}` },
    })
    if (!resp.ok && resp.status !== 206) {
      throw new Error(`Chunk download failed: ${resp.statusText}`)
    }
    const blob = await resp.blob()
    chunks.push(blob)
    downloaded += blob.size
    if (blob.size === 0) break
  }

  const finalBlob = new Blob(chunks)
  downloadBlob(finalBlob, dispositionFilename)
}

/**
 * Download a file, automatically choosing between
 * a simple fetch and a chunked download based on chunkSize
 * @param url - The API URL to download from
 * @param filename - The filename to save as
 * @param chunkSize - Maximum bytes per request (0 = no chunking)
 */
export async function downloadFile(
  url: string,
  filename: string,
  chunkSize: number,
): Promise<void> {
  if (chunkSize > 0) {
    return downloadChunked(url, filename, chunkSize)
  }
  const resp = await fetch(url)
  await downloadFromResponse(resp, filename)
}
