import { useEffect, useState, useRef, useCallback } from 'react'
import { FaTimes, FaMusic, FaPlay, FaPause, FaVolumeUp, FaVolumeMute, FaExpand, FaCopy, FaCheck } from 'react-icons/fa'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import vscDarkPlus from 'react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus'
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript'
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript'
import tsx from 'react-syntax-highlighter/dist/esm/languages/prism/tsx'
import jsx from 'react-syntax-highlighter/dist/esm/languages/prism/jsx'
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python'
import ruby from 'react-syntax-highlighter/dist/esm/languages/prism/ruby'
import java from 'react-syntax-highlighter/dist/esm/languages/prism/java'
import c from 'react-syntax-highlighter/dist/esm/languages/prism/c'
import cpp from 'react-syntax-highlighter/dist/esm/languages/prism/cpp'
import csharp from 'react-syntax-highlighter/dist/esm/languages/prism/csharp'
import go from 'react-syntax-highlighter/dist/esm/languages/prism/go'
import rust from 'react-syntax-highlighter/dist/esm/languages/prism/rust'
import swift from 'react-syntax-highlighter/dist/esm/languages/prism/swift'
import kotlin from 'react-syntax-highlighter/dist/esm/languages/prism/kotlin'
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash'
import powershell from 'react-syntax-highlighter/dist/esm/languages/prism/powershell'
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json'
import yaml from 'react-syntax-highlighter/dist/esm/languages/prism/yaml'
import xml from 'react-syntax-highlighter/dist/esm/languages/prism/markup'
import css from 'react-syntax-highlighter/dist/esm/languages/prism/css'
import scss from 'react-syntax-highlighter/dist/esm/languages/prism/scss'
import sass from 'react-syntax-highlighter/dist/esm/languages/prism/sass'
import less from 'react-syntax-highlighter/dist/esm/languages/prism/less'
import graphql from 'react-syntax-highlighter/dist/esm/languages/prism/graphql'
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql'
import toml from 'react-syntax-highlighter/dist/esm/languages/prism/toml'
import ini from 'react-syntax-highlighter/dist/esm/languages/prism/ini'
import diff from 'react-syntax-highlighter/dist/esm/languages/prism/diff'
import batch from 'react-syntax-highlighter/dist/esm/languages/prism/batch'
import { authFetch as fetch } from '../utils/api'

SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('typescript', typescript)
SyntaxHighlighter.registerLanguage('tsx', tsx)
SyntaxHighlighter.registerLanguage('jsx', jsx)
SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('ruby', ruby)
SyntaxHighlighter.registerLanguage('java', java)
SyntaxHighlighter.registerLanguage('c', c)
SyntaxHighlighter.registerLanguage('cpp', cpp)
SyntaxHighlighter.registerLanguage('csharp', csharp)
SyntaxHighlighter.registerLanguage('go', go)
SyntaxHighlighter.registerLanguage('rust', rust)
SyntaxHighlighter.registerLanguage('swift', swift)
SyntaxHighlighter.registerLanguage('kotlin', kotlin)
SyntaxHighlighter.registerLanguage('bash', bash)
SyntaxHighlighter.registerLanguage('powershell', powershell)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('yaml', yaml)
SyntaxHighlighter.registerLanguage('xml', xml)
SyntaxHighlighter.registerLanguage('html', xml)
SyntaxHighlighter.registerLanguage('css', css)
SyntaxHighlighter.registerLanguage('scss', scss)
SyntaxHighlighter.registerLanguage('sass', sass)
SyntaxHighlighter.registerLanguage('less', less)
SyntaxHighlighter.registerLanguage('graphql', graphql)
SyntaxHighlighter.registerLanguage('sql', sql)
SyntaxHighlighter.registerLanguage('toml', toml)
SyntaxHighlighter.registerLanguage('ini', ini)
SyntaxHighlighter.registerLanguage('diff', diff)
SyntaxHighlighter.registerLanguage('batch', batch)

// A markdown grammar that does NOT embed the HTML/markup tokenizer.
// Prism's built-in markdown grammar inherits from markup, which tokenizes
// <img> and other inline HTML as block-level nodes and inserts newlines.
// refractor (PrismLight's backend) requires the function to have a displayName.
function markdownSafeLang(Prism: any) {
  Prism.languages['markdown-safe'] = {
    'code-block': {
      pattern: /^(```+)[^`\n]*\n[\s\S]*?\n\1/m,
      greedy: true,
      alias: 'string',
    },
    'code-inline': {
      pattern: /`[^`\n]+`/,
      greedy: true,
      alias: 'string',
    },
    'heading': {
      pattern: /^#{1,6}(?= ).+/m,
      alias: 'keyword',
    },
    'image': {
      pattern: /!\[[^\]\n]*\]\([^)\n]+\)/,
      greedy: true,
      alias: 'attr-value',
    },
    'link': {
      pattern: /\[[^\]\n]*\]\([^)\n]+\)/,
      greedy: true,
      alias: 'attr-value',
    },
    'bold': {
      pattern: /\*\*(?:[^*\n]|\*(?!\*))+\*\*|__(?:[^_\n]|_(?!_))+__/,
      alias: 'bold',
    },
    'italic': {
      pattern: /\*(?:[^*\n])+\*|_(?:[^_\n])+_/,
      alias: 'italic',
    },
    'blockquote': {
      pattern: /^>[ \t].*/m,
      alias: 'comment',
    },
    'list-marker': {
      pattern: /^[ \t]*(?:[-*+]|\d+[.)]) /m,
      alias: 'punctuation',
    },
    'table-separator': {
      pattern: /^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/m,
      alias: 'comment',
    },
    'table-pipe': {
      pattern: /\|/,
      alias: 'punctuation',
    },
    'hr': {
      pattern: /^(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$/m,
      alias: 'comment',
    },
  }
}
markdownSafeLang.displayName = 'markdown-safe'
SyntaxHighlighter.registerLanguage('markdown-safe', markdownSafeLang)

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

// Maps file extension to a Prism language identifier
const EXT_TO_LANGUAGE: Record<string, string> = {
  js: 'javascript', ts: 'typescript', tsx: 'tsx', jsx: 'jsx',
  py: 'python', rb: 'ruby', java: 'java', c: 'c', cpp: 'cpp',
  h: 'c', hpp: 'cpp', cs: 'csharp', go: 'go', rs: 'rust',
  swift: 'swift', kt: 'kotlin', sh: 'bash', bash: 'bash',
  zsh: 'bash', bat: 'batch', ps1: 'powershell',
  json: 'json', yaml: 'yaml', yml: 'yaml', xml: 'xml',
  html: 'html', htm: 'html', css: 'css', scss: 'scss',
  sass: 'sass', less: 'less', graphql: 'graphql', gql: 'graphql',
  sql: 'sql', md: 'markdown-safe', rst: 'plain', tex: 'plain',
  toml: 'toml', ini: 'ini', diff: 'diff', patch: 'diff',
  srt: 'plain', ass: 'plain', vtt: 'plain', log: 'plain',
  env: 'bash', conf: 'bash', cfg: 'bash', properties: 'bash',
  tsv: 'plain', txt: 'plain',
}

const RAINBOW_COLUMN_COLORS = [
  'text-[#60a5fa]', // blue-400
  'text-[#34d399]', // emerald-400
  'text-[#f87171]', // red-400
  'text-[#fbbf24]', // amber-400
  'text-[#a78bfa]', // violet-400
  'text-[#fb923c]', // orange-400
  'text-[#38bdf8]', // sky-400
  'text-[#4ade80]', // green-400
  'text-[#f472b6]', // pink-400
  'text-[#facc15]', // yellow-400
]

function CsvViewer({ content }: { content: string }) {
  const lines = content.split('\n')
  const delimiter = content.includes('\t') ? '\t' : ','

  const parsedRows = lines
    .filter(l => l.trim() !== '')
    .map(line => {
      // Simple CSV parse: handle quoted fields
      const fields: string[] = []
      let cur = ''
      let inQuotes = false
      for (let i = 0; i < line.length; i++) {
        const ch = line[i]
        if (ch === '"') {
          if (inQuotes && line[i + 1] === '"') { cur += '"'; i++ }
          else { inQuotes = !inQuotes }
        } else if (ch === delimiter && !inQuotes) {
          fields.push(cur); cur = ''
        } else {
          cur += ch
        }
      }
      fields.push(cur)
      return fields
    })

  if (parsedRows.length === 0) return <pre className="text-sm text-text font-mono">{content}</pre>

  const [header, ...rows] = parsedRows

  return (
    <table className="text-xs font-mono border-collapse min-w-full">
      <thead>
        <tr className="border-b border-surface-dark/60 bg-surface-dark/40">
          {header.map((cell, ci) => (
            <th
              key={ci}
              className={`px-3 py-1.5 text-left font-semibold break-words max-w-[14rem] ${RAINBOW_COLUMN_COLORS[ci % RAINBOW_COLUMN_COLORS.length]}`}
            >
              {cell}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, ri) => (
          <tr key={ri} className={ri % 2 === 0 ? '' : 'bg-surface-dark/20'}>
            {row.map((cell, ci) => (
              <td
                key={ci}
                className={`px-3 py-1 break-words max-w-[14rem] ${RAINBOW_COLUMN_COLORS[ci % RAINBOW_COLUMN_COLORS.length]}`}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function TextViewer({ content, mediaType }: { content: string; mediaType: string }) {
  const ext = mediaType.toLowerCase()
  const isCsv = ext === 'csv'
  const isTsv = ext === 'tsv'

  if (isCsv || isTsv) {
    return (
      <div className="relative w-[80vw] max-h-[75vh]">
        <CopyButton text={content} />
        <div className="w-full h-full overflow-auto bg-surface-dark rounded-lg p-5 pb-8">
          <CsvViewer content={content} />
        </div>
      </div>
    )
  }

  const language = EXT_TO_LANGUAGE[ext] ?? 'plain'
  const usePlain = language === 'plain'

  return (
    <div className="relative w-[80vw] max-h-[75vh]">
      <CopyButton text={content} />
      {usePlain ? (
        <pre className="w-full h-full overflow-auto text-sm text-text bg-surface-dark rounded-lg p-5 pb-8 whitespace-pre font-mono leading-relaxed">
          {content}
        </pre>
      ) : (
        <div className="w-full h-full overflow-auto rounded-lg text-sm [&>pre]:!m-0 [&>pre]:!rounded-lg [&>pre]:!max-h-[75vh] [&>pre]:!overflow-auto">
          <SyntaxHighlighter
            language={language}
            style={vscDarkPlus}
            customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.8125rem', lineHeight: '1.6', paddingBottom: '2rem', overflowX: 'auto' }}
          >
            {content}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
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
  const [mediaUrl, setMediaUrl] = useState<string | null>(null)
  const [mediaLoading, setMediaLoading] = useState(false)

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
    if (!previewType || previewType === 'text') return
    setMediaLoading(true)
    let objectUrl: string | null = null
    fetch(url)
      .then(r => r.blob())
      .then(blob => {
        const normalizedBlob = previewType === 'pdf'
          ? new Blob([blob], { type: 'application/pdf' })
          : blob
        objectUrl = URL.createObjectURL(normalizedBlob)
        setMediaUrl(objectUrl)
      })
      .catch(() => setMediaUrl(null))
      .finally(() => setMediaLoading(false))
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      setMediaUrl(null)
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
            mediaLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : mediaUrl
                ? <img
                    src={mediaUrl}
                    alt={filename}
                    className="max-w-[80vw] max-h-[75vh] object-contain rounded"
                  />
                : <p className="text-text-muted text-sm">Failed to load image preview.</p>
          )}
          {previewType === 'video' && (
            mediaLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : mediaUrl
                ? <VideoPlayer src={mediaUrl} />
                : <p className="text-text-muted text-sm">Failed to load video preview.</p>
          )}
          {previewType === 'audio' && (
            mediaLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : mediaUrl
                ? <div className="flex flex-col items-center gap-6 w-[36rem] max-w-[80vw] px-4">
                    <div className="w-28 h-28 rounded-full bg-primary/10 flex items-center justify-center">
                      <FaMusic className="text-4xl text-primary" />
                    </div>
                    <span className="text-sm text-text-muted font-medium text-center truncate max-w-full" title={filename}>
                      {filename}
                    </span>
                    <AudioPlayer src={mediaUrl} mediaType={mediaType} />
                  </div>
                : <p className="text-text-muted text-sm">Failed to load audio preview.</p>
          )}
          {previewType === 'pdf' && (
            mediaLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : mediaUrl
                ? <iframe
                    src={mediaUrl}
                    title={filename}
                    className="w-[80vw] h-[75vh] rounded border-0"
                  />
                : <p className="text-text-muted text-sm">Failed to load PDF.</p>
          )}
          {previewType === 'text' && (
            textLoading
              ? <p className="text-text-muted text-sm">Loading...</p>
              : <TextViewer content={textContent ?? ''} mediaType={mediaType} />
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
