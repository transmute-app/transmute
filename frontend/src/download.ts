/**
 * Download utilities for the frontend
 * Provides reusable download helpers to replace manual anchor element creation
 */

/**
 * Download a blob with a specified filename
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}

/**
 * Download content from a fetch response
 * Automatically handles blob extraction and optional filename extraction
 */
export async function downloadFromResponse(
  response: Response,
  fallbackFilename: string = 'download'
): Promise<void> {
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status} ${response.statusText}`)
  }

  const blob = await response.blob()

  // Try to extract filename from Content-Disposition header
  let filename = fallbackFilename
  const contentDisposition = response.headers.get('Content-Disposition')
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (filenameMatch && filenameMatch[1]) {
      // Remove quotes if present
      filename = filenameMatch[1].replace(/['"]/g, '')
    }
  }

  downloadBlob(blob, filename)
}
