/**
 * Download utilities for handling blob downloads
 */

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
