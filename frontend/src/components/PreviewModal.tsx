import { useEffect, useState, useRef, useCallback } from 'react'
import { FaTimes, FaMusic, FaPlay, FaPause, FaVolumeUp, FaVolumeMute, FaExpand, FaCopy, FaCheck } from 'react-icons/fa'

const PREVIEWABLE_IMAGE = new Set([
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif',
])
const PREVIEWABLE_VIDEO = new Set(['mp4', 'webm', 'ogg'])
const PREVIEWABLE_AUDIO = new Set(['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a', 'opus'])
const PREVIEWABLE_PDF = new Set(['pdf'])
const PREVIEWABLE_TEXT = new Set([
  'txt', 'csv', 'json', 'xml', 'html', 'htm', 'css', 'js', 'ts',
  'md', 'yaml', 'yml', 'log', 'srt', 'ass', 'vtt',
  'ini', 'toml', 'conf', 'cfg', 'env', 'properties',
  'sql', 'py', 'rb', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go',
  'rs', 'swift', 'kt', 'sh', 'bash', 'zsh', 'bat', 'ps1',
  'tsx', 'jsx', 'scss', 'sass', 'less', 'graphql', 'gql',
  'rst', 'tex', 'tsv', 'diff', 'patch',
])

type PreviewType = 'image' | 'video' | 'audio' | 'pdf' | 'text' | null

export function getPreviewType(mediaType: string): PreviewType {
  const mt = mediaType.toLowerCase()
  if (PREVIEWABLE_IMAGE.has(mt)) return 'image'
  if (PREVIEWABLE_VIDEO.has(mt)) return 'video'
  if (PREVIEWABLE_AUDIO.has(mt)) return 'audio'
  if (PREVIEWABLE_PDF.has(mt)) return 'pdf'
  if (PREVIEWABLE_TEXT.has(mt)) return 'text'
  return null
}

export function isPreviewable(mediaType: string): boolean {
  return getPreviewType(mediaType) !== null
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function useMediaControls(mediaRef: React.RefObject<HTMLMediaElement | null>) {
  const trackRef = useRef<HTMLDivElement>(null)
  const volumeRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  const durationRef = useRef(0)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [muted, setMuted] = useState(false)

  const setTrustedDuration = (d: number) => {
    if (isFinite(d) && d > 0) {
      setDuration(d)
      durationRef.current = d
    }
  }

  const togglePlay = () => {
    const el = mediaRef.current
    if (!el) return
    if (playing) { el.pause() } else { el.play() }
    setPlaying(!playing)
  }

  const handleTimeUpdate = () => {
    const el = mediaRef.current
    if (!el) return
    if (!draggingRef.current) setCurrentTime(el.currentTime)
    // If currentTime exceeds reported duration, the duration was wrong — fix it
    if (el.currentTime > durationRef.current && isFinite(el.currentTime)) {
      setTrustedDuration(el.currentTime)
    }
  }

  const seekToX = useCallback((clientX: number) => {
    const el = mediaRef.current
    const track = trackRef.current
    if (!el || !track || !durationRef.current) return
    const rect = track.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    el.currentTime = pct * durationRef.current
    setCurrentTime(pct * durationRef.current)
  }, [mediaRef])

  const handleSeekDown = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    draggingRef.current = true
    seekToX(e.clientX)

    const onMove = (ev: MouseEvent) => {
      ev.preventDefault()
      seekToX(ev.clientX)
    }
    const onUp = () => {
      draggingRef.current = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  const applyVolume = (clientX: number, el: HTMLDivElement) => {
    const rect = el.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    setVolume(pct)
    setMuted(pct === 0)
    if (mediaRef.current) mediaRef.current.volume = pct
  }

  const handleVolumeDown = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    const el = volumeRef.current
    if (!el) return
    applyVolume(e.clientX, el)

    const onMove = (ev: MouseEvent) => {
      ev.preventDefault()
      applyVolume(ev.clientX, el!)
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  const toggleMute = () => {
    const el = mediaRef.current
    if (!el) return
    if (muted) {
      el.volume = volume || 0.5
      setVolume(volume || 0.5)
    } else {
      el.volume = 0
    }
    setMuted(!muted)
  }

  const updateDuration = () => {
    const el = mediaRef.current
    if (el) setTrustedDuration(el.duration)
  }

  const onEnded = () => {
    const el = mediaRef.current
    if (el) {
      // On ended, currentTime is the real duration — trust it over the header
      setTrustedDuration(el.currentTime)
      setCurrentTime(el.currentTime)
    }
    setPlaying(false)
  }

  const progress = duration ? Math.min(currentTime / duration, 1) : 0

  return {
    trackRef, volumeRef, playing, currentTime, duration, volume, muted, progress,
    togglePlay, handleTimeUpdate, handleSeekDown, handleVolumeDown, toggleMute,
    updateDuration, onEnded,
  }
}

function MediaControlsBar({ controls, showFullscreen, onFullscreen, hideDuration }: {
  controls: ReturnType<typeof useMediaControls>
  showFullscreen?: boolean
  onFullscreen?: () => void
  hideDuration?: boolean
}) {
  const { trackRef, volumeRef, playing, currentTime, duration, volume, muted, progress,
    togglePlay, handleSeekDown, handleVolumeDown, toggleMute } = controls

  return (
    <div className="flex items-center gap-3 w-full">
      <button
        onClick={togglePlay}
        className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-text hover:bg-primary-dark transition duration-200 flex-shrink-0"
      >
        {playing ? <FaPause className="text-xs" /> : <FaPlay className="text-xs ml-0.5" />}
      </button>

      <span className="text-xs text-text-muted tabular-nums w-10 text-right flex-shrink-0">{formatTime(currentTime)}</span>

      <div
        ref={trackRef}
        className="flex-1 h-5 flex items-center cursor-pointer relative select-none"
        onMouseDown={handleSeekDown}
      >
        <div className="w-full h-1.5 bg-surface-dark rounded-full relative">
          <div
            className="h-full bg-primary rounded-full"
            style={{ width: `${progress * 100}%` }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 bg-primary rounded-full shadow-md pointer-events-none"
            style={{ left: `calc(${progress * 100}% - 7px)` }}
          />
        </div>
      </div>

      {!hideDuration && (
        <span className="text-xs text-text-muted tabular-nums w-10 flex-shrink-0">{formatTime(duration)}</span>
      )}

      <button onClick={toggleMute} className="text-text-muted hover:text-text transition duration-200 flex-shrink-0">
        {muted || volume === 0 ? <FaVolumeMute /> : <FaVolumeUp />}
      </button>
      <div
        ref={volumeRef}
        className="w-20 h-5 flex items-center cursor-pointer relative select-none flex-shrink-0"
        onMouseDown={handleVolumeDown}
      >
        <div className="w-full h-1.5 bg-surface-dark rounded-full relative">
          <div
            className="h-full bg-text-muted rounded-full"
            style={{ width: `${(muted ? 0 : volume) * 100}%` }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-text-muted rounded-full shadow-md pointer-events-none"
            style={{ left: `calc(${(muted ? 0 : volume) * 100}% - 5px)` }}
          />
        </div>
      </div>

      {showFullscreen && onFullscreen && (
        <button
          onClick={onFullscreen}
          className="text-text-muted hover:text-text transition duration-200 flex-shrink-0"
          title="Fullscreen"
        >
          <FaExpand />
        </button>
      )}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-3 right-3 z-10 p-2 rounded-lg bg-surface-light/80 hover:bg-surface-light text-text-muted hover:text-text transition duration-200 backdrop-blur-sm"
      title={copied ? 'Copied!' : 'Copy to clipboard'}
    >
      {copied ? <FaCheck className="text-success text-sm" /> : <FaCopy className="text-sm" />}
    </button>
  )
}

function AudioPlayer({ src, mediaType }: { src: string; mediaType: string }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const controls = useMediaControls(audioRef)
  const hideDuration = mediaType === 'aac'

  return (
    <div className="w-full">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={controls.handleTimeUpdate}
        onLoadedMetadata={controls.updateDuration}
        onDurationChange={controls.updateDuration}
        onEnded={controls.onEnded}
      />
      <MediaControlsBar controls={controls} hideDuration={hideDuration} />
    </div>
  )
}

function VideoPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const controls = useMediaControls(videoRef)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const onFsChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current)
    }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  const handleFullscreen = () => {
    const el = containerRef.current
    if (!el) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      el.requestFullscreen()
    }
  }

  return (
    <div
      ref={containerRef}
      className={`flex flex-col rounded overflow-hidden bg-black ${isFullscreen ? 'w-screen h-screen' : ''}`}
    >
      <video
        ref={videoRef}
        src={src}
        className={`cursor-pointer ${isFullscreen ? 'flex-1 w-full object-contain min-h-0' : 'max-w-[80vw] max-h-[65vh]'}`}
        onClick={controls.togglePlay}
        onTimeUpdate={controls.handleTimeUpdate}
        onLoadedMetadata={controls.updateDuration}
        onDurationChange={controls.updateDuration}
        onEnded={controls.onEnded}
      />
      <div className="w-full px-3 py-2 bg-surface-dark/80 flex-shrink-0">
        <MediaControlsBar controls={controls} showFullscreen onFullscreen={handleFullscreen} />
      </div>
    </div>
  )
}

interface PreviewModalProps {
  fileId: string
  filename: string
  mediaType: string
  onClose: () => void
}

function PreviewModal({ fileId, filename, mediaType, onClose }: PreviewModalProps) {
  const previewType = getPreviewType(mediaType)
  const url = `/api/files/${encodeURIComponent(fileId)}`
  const [textContent, setTextContent] = useState<string | null>(null)
  const [textLoading, setTextLoading] = useState(false)

  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  useEffect(() => {
    if (previewType !== 'text') return
    setTextLoading(true)
    fetch(url)
      .then(r => r.text())
      .then(setTextContent)
      .catch(() => setTextContent('Failed to load file content.'))
      .finally(() => setTextLoading(false))
  }, [url, previewType])

  useEffect(() => {
    if (previewType !== 'pdf') return
    setPdfLoading(true)
    let objectUrl: string | null = null
    fetch(url)
      .then(r => r.blob())
      .then(blob => {
        const pdfBlob = new Blob([blob], { type: 'application/pdf' })
        objectUrl = URL.createObjectURL(pdfBlob)
        setPdfUrl(objectUrl)
      })
      .catch(() => setPdfUrl(null))
      .finally(() => setPdfLoading(false))
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url, previewType])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative bg-surface-light rounded-xl shadow-2xl border border-surface-dark max-w-[90vw] max-h-[90vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-4 px-5 py-3.5 border-b border-surface-dark bg-surface-dark/30">
          <span className="text-sm font-medium text-text truncate max-w-[60vw]" title={filename}>
            {filename}
          </span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-dark transition duration-200 flex-shrink-0"
            aria-label="Close preview"
          >
            <FaTimes />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-auto p-6 flex items-center justify-center min-w-[300px] min-h-[200px]">
          {previewType === 'image' && (
            <img
              src={url}
              alt={filename}
              className="max-w-[80vw] max-h-[75vh] object-contain rounded"
            />
          )}
          {previewType === 'video' && (
            <VideoPlayer src={url} />
          )}
          {previewType === 'audio' && (
            <div className="flex flex-col items-center gap-6 w-[36rem] max-w-[80vw] px-4">
              <div className="w-28 h-28 rounded-full bg-primary/10 flex items-center justify-center">
                <FaMusic className="text-4xl text-primary" />
              </div>
              <span className="text-sm text-text-muted font-medium text-center truncate max-w-full" title={filename}>
                {filename}
              </span>
              <AudioPlayer src={url} mediaType={mediaType} />
            </div>
          )}
          {previewType === 'pdf' && (
            pdfLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : pdfUrl
                ? <iframe
                    src={pdfUrl}
                    title={filename}
                    className="w-[80vw] h-[75vh] rounded border-0"
                  />
                : <p className="text-text-muted text-sm">Failed to load PDF.</p>
          )}
          {previewType === 'text' && (
            textLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : <div className="relative w-[80vw] max-h-[75vh]">
                  <CopyButton text={textContent ?? ''} />
                  <pre className="w-full h-full overflow-auto text-sm text-text bg-surface-dark rounded-lg p-5 whitespace-pre-wrap break-words font-mono leading-relaxed">{textContent}</pre>
                </div>
          )}
          {!previewType && (
            <p className="text-text-muted text-sm">Preview not available for this file type.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default PreviewModal
