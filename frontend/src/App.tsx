import { useState } from 'react'

function App() {
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
      // Set default format if available
      if (data.metadata?.compatible_formats?.length > 0) {
        setSelectedFormat(data.metadata.compatible_formats[0])
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <h1 className="text-4xl font-bold text-center text-indigo-600 mb-6">
          Transmute
        </h1>
        <p className="text-gray-600 text-center mb-8">
          File conversion made simple
        </p>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {uploading ? 'Uploading...' : 'Select a file to upload'}
            </label>
            <input
              type="file"
              onChange={handleFileSelect}
              disabled={uploading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-semibold
                file:bg-indigo-50 file:text-indigo-700
                hover:file:bg-indigo-100
                cursor-pointer
                disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          {uploading && (
            <div className="text-sm text-indigo-600 font-medium">
              Uploading file...
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {selectedFile && uploadResult && (
            <div className="space-y-4">
              <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <p className="text-sm font-semibold text-gray-700 mb-1">Selected File</p>
                <p className="text-xs text-gray-600">{selectedFile.name}</p>
                <p className="text-xs text-gray-500">({(selectedFile.size / 1024).toFixed(2)} KB)</p>
              </div>

              {uploadResult.metadata?.compatible_formats && uploadResult.metadata.compatible_formats.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Convert to:
                  </label>
                  <select
                    value={selectedFormat}
                    onChange={(e) => setSelectedFormat(e.target.value)}
                    className="block w-full px-3 py-2 bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    {uploadResult.metadata.compatible_formats.map((format: string) => (
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
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {converting ? 'Converting...' : 'Convert'}
              </button>

              {conversionResult && (
                <div className="space-y-3">
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
                    <p className="font-semibold mb-1">Conversion complete!</p>
                    <p className="text-xs">Ready to download</p>
                  </div>
                  <button
                    onClick={handleDownload}
                    className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg"
                  >
                    Download Converted File
                  </button>
                </div>
              )}
            </div>
          )}

          {uploadResult && !selectedFile && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
              <p className="font-semibold mb-1">Upload successful!</p>
              <p className="text-xs">File ID: {uploadResult.metadata?.id}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
