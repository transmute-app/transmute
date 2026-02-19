import { useState } from 'react'

function Converter() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedFormat, setSelectedFormat] = useState<string>('')
  const [converting, setConverting] = useState(false)
  const [conversionResult, setConversionResult] = useState<any>(null)

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setSelectedFile(file)
    setUploadResult(null)
    setError(null)
    setSelectedFormat('')
    setConversionResult(null)
    setUploading(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/api/files/', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`)
      }

      const data = await response.json()
      setUploadResult(data)
      // Reset file input for next upload
      event.target.value = ''
      // Set default format if available (alphabetically first)
      if (data.metadata?.compatible_formats?.length > 0) {
        const sortedFormats = [...data.metadata.compatible_formats].sort()
        setSelectedFormat(sortedFormats[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleConvert = async () => {
    if (!uploadResult?.metadata?.id || !selectedFormat) return

    setConverting(true)
    setError(null)

    // Get input format from the file extension (remove the leading dot)
    const inputFormat = uploadResult.metadata.extension?.replace(/^\./, '') || ''

    try {
      const response = await fetch('/api/conversions/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: uploadResult.metadata.id,
          input_format: inputFormat,
          output_format: selectedFormat,
        }),
      })

      if (!response.ok) {
        throw new Error(`Conversion failed: ${response.statusText}`)
      }

      const data = await response.json()
      setConversionResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Conversion failed')
    } finally {
      setConverting(false)
    }
  }

  const handleDownload = async () => {
    if (!conversionResult?.id) return

    try {
      const response = await fetch(`/api/files/${conversionResult.id}`)
      if (!response.ok) {
        throw new Error('Download failed')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      
      // Construct filename: replace original extension with new extension
      let filename = conversionResult.original_filename || 'download'
      const lastDotIndex = filename.lastIndexOf('.')
      if (lastDotIndex > 0) {
        filename = filename.substring(0, lastDotIndex)
      }
      // Extension from backend already includes the dot
      const extension = conversionResult.extension || ''
      filename += extension
      
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    }
  }

  return (
    <div className="h-full bg-gradient-to-br from-surface-dark to-surface-light flex items-center justify-center p-4">
      <div className="bg-surface-light rounded-lg shadow-xl p-8 max-w-xl w-full border border-surface-dark">
        <h1 className="text-4xl font-bold text-center text-primary mb-6">
          Transmute
        </h1>
        
        <div className="space-y-4">
          {!uploadResult || conversionResult ? (
            <div>
              <input
                type="file"
                onChange={handleFileSelect}
                disabled={uploading}
                className="block w-full text-sm text-text-muted
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-lg file:border-0
                  file:text-sm file:font-semibold
                  file:bg-primary/20 file:text-primary
                  hover:file:bg-primary/30
                  cursor-pointer
                  disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
          ) : (
            <div className="p-3 bg-surface-dark/50 border border-surface-dark rounded-lg">
              <div className="flex justify-between items-start mb-2">
                <p className="text-sm font-semibold text-text">Selected File</p>
                <label className="text-xs text-primary hover:text-primary-light cursor-pointer font-medium">
                  Change File
                  <input
                    type="file"
                    onChange={handleFileSelect}
                    disabled={uploading}
                    className="hidden"
                  />
                </label>
              </div>
              <p className="text-xs text-text-muted">{selectedFile?.name}</p>
              <p className="text-xs text-text-muted/70">({((selectedFile?.size || 0) / 1024).toFixed(2)} KB)</p>
            </div>
          )}

          {uploading && (
            <div className="text-sm text-primary font-medium">
              Uploading file...
            </div>
          )}

          {error && (
            <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm">
              {error}
            </div>
          )}

          {selectedFile && uploadResult && !conversionResult && (
            <div className="space-y-4">

              {uploadResult.metadata?.compatible_formats && uploadResult.metadata.compatible_formats.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-text mb-2">
                    Convert to:
                  </label>
                  <select
                    value={selectedFormat}
                    onChange={(e) => setSelectedFormat(e.target.value)}
                    className="block w-full px-3 py-2 bg-surface-dark border border-surface-dark text-text rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-sm"
                  >
                    {[...uploadResult.metadata.compatible_formats].sort().map((format: string) => (
                      <option key={format} value={format}>
                        {format}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <button
                onClick={handleConvert}
                disabled={converting || !selectedFormat || conversionResult !== null}
                className="w-full bg-primary hover:bg-primary-dark text-text font-semibold py-3 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {converting ? 'Converting...' : 'Convert'}
              </button>
            </div>
          )}

          {conversionResult && (
            <div className="space-y-3">
              <div className="p-3 bg-success/20 border border-success rounded-lg text-success-light text-sm">
                <p className="font-semibold mb-1">Converted File</p>
                <p className="text-xs text-text-muted">
                  {(() => {
                    let filename = conversionResult.original_filename || 'download'
                    const lastDotIndex = filename.lastIndexOf('.')
                    if (lastDotIndex > 0) {
                      filename = filename.substring(0, lastDotIndex)
                    }
                    return filename + (conversionResult.extension || '')
                  })()}
                <p className="text-xs text-text-muted/70">({(conversionResult.size_bytes / 1024).toFixed(2)} KB)</p>
                </p>
              </div>
              <button
                onClick={handleDownload}
                className="w-full bg-success hover:bg-success-dark text-white font-semibold py-3 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg"
              >
                Download Converted File
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Converter
