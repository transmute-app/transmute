const COMPOUND_EXTENSIONS = ['.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst']

/**
 * Strip the extension from a filename, handling compound extensions like .tar.gz.
 * Returns the base name without extension.
 */
export function stripExtension(filename: string): string {
  const lower = filename.toLowerCase()
  for (const ext of COMPOUND_EXTENSIONS) {
    if (lower.endsWith(ext)) {
      return filename.substring(0, filename.length - ext.length)
    }
  }
  const dot = filename.lastIndexOf('.')
  return dot > 0 ? filename.substring(0, dot) : filename
}
