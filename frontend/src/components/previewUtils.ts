const PREVIEWABLE_IMAGE = new Set([
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif',
])
const PREVIEWABLE_VIDEO = new Set(['mp4', 'webm', 'ogg'])
const PREVIEWABLE_AUDIO = new Set(['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a', 'opus'])
const PREVIEWABLE_PDF = new Set(['pdf', 'pdf/a', 'pdf/x', 'pdf/e', 'pdf/ua', 'pdf/vt'])
const PREVIEWABLE_TEXT = new Set([
  'txt', 'csv', 'json', 'xml', 'html', 'htm', 'css', 'js', 'ts',
  'md', 'yaml', 'yml', 'log', 'srt', 'ass', 'vtt',
  'ini', 'toml', 'conf', 'cfg', 'env', 'properties',
  'sql', 'py', 'rb', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go',
  'rs', 'swift', 'kt', 'sh', 'bash', 'zsh', 'bat', 'ps1',
  'tsx', 'jsx', 'scss', 'sass', 'less', 'graphql', 'gql',
  'rst', 'tex', 'tsv', 'diff', 'patch', 'toon', 'jsonl'
])

export type PreviewType = 'image' | 'video' | 'audio' | 'pdf' | 'text' | null

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