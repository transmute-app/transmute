import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import Converter from './Converter'
import * as api from '../utils/api'

function renderConverter() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter>
        <Converter />
      </MemoryRouter>
    </I18nextProvider>,
  )
}

function urlFromFetchInput(input: RequestInfo | URL) {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

function urlMatchesPath(input: RequestInfo | URL, path: string) {
  const url = urlFromFetchInput(input)
  return url === path || url.endsWith(path)
}

function createDataTransfer(files: File[] = [], text = '', opts: { populateItemsFromFiles?: boolean; itemsOnly?: boolean } = {}) {
  const fileList = opts.itemsOnly ? [] : [...files]
  const items: { kind: string; type: string; file?: File; getAsFile?: () => File | null }[] = []
  const itemsList: { add(file: File): null; length: number; [Symbol.iterator](): Iterator<typeof items[number]> } = {
    add(file: File) {
      fileList.push(file)
      items.push({ kind: 'file', type: file.type, file, getAsFile: () => file })
      return null
    },
    get length() { return items.length },
    [Symbol.iterator]() { return items[Symbol.iterator]() },
  }
  const dt = {
    files: Object.assign(fileList, {
      length: fileList.length,
      item(i: number) { return fileList[i] ?? null },
    }) as unknown as FileList,
    items: itemsList as unknown as DataTransferItemList,
    getData(type: string) { return type === 'text/plain' ? text : '' },
    setData(type: string, value: string) { if (type === 'text/plain') text = value },
  }

  if (opts.populateItemsFromFiles) {
    for (const file of files) {
      items.push({ kind: 'file', type: file.type, file, getAsFile: () => file })
    }
  }
  return dt as unknown as DataTransfer
}

function dispatchPaste(dt: DataTransfer) {
  const event = new Event('paste', { bubbles: true })
  Object.defineProperty(event, 'clipboardData', { value: dt })
  fireEvent(document.body, event)
}

function dispatchDrop(dropZone: HTMLElement, dt: DataTransfer) {
  const event = new Event('drop', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'dataTransfer', { value: dt })
  fireEvent(dropZone, event)
}

const pasteFiles = (files: File[]) => dispatchPaste(createDataTransfer(files))
const pasteItems = (files: File[]) =>
  dispatchPaste(createDataTransfer(files, '', { populateItemsFromFiles: true, itemsOnly: true }))
const pasteText = (text: string) => dispatchPaste(createDataTransfer([], text))
const dropFiles = (dropZone: HTMLElement, files: File[]) => dispatchDrop(dropZone, createDataTransfer(files))

function selectFilesViaInput(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  Object.defineProperty(input, 'value', {
    value: files.length > 0 ? `C:\\fakepath\\${files[0].name}` : '',
    configurable: true,
    writable: true,
  })
  fireEvent.change(input)
}

const findDropZone = () => document.querySelector('input[type="file"]')!.closest('label')!
const findFileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement

function makeUploadResponse(filename: string, id: string) {
  return {
    metadata: {
      id,
      original_filename: filename,
      media_type: 'text',
      extension: '.txt',
      size_bytes: 12,
      created_at: '2026-07-25T00:00:00Z',
      compatible_formats: { txt: ['md'] },
    },
  }
}

function defaultFetchResponse(url: string): Response | undefined {
  if (url === '/api/settings') return new Response(JSON.stringify({ auto_download: false }), { status: 200 })
  if (url === '/api/default-formats') return new Response(JSON.stringify({ defaults: [], aliases: {} }), { status: 200 })
  if (url === '/api/default-qualities') return new Response(JSON.stringify({ defaults: [] }), { status: 200 })
  if (url === '/api/compressors') return new Response(JSON.stringify({ compressors: [] }), { status: 200 })
  if (url === '/api/default-compression-levels') return new Response(JSON.stringify({ defaults: [] }), { status: 200 })
  if (url === '/api/files/url') return new Response(JSON.stringify({ files: [] }), { status: 200 })
  return undefined
}

describe('Converter drop-zone interactions', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(async () => {
    await i18n.changeLanguage('en')
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async (input) => {
      const url = urlFromFetchInput(input)
      const defaultResponse = defaultFetchResponse(url)
      if (defaultResponse) return defaultResponse
      if (urlMatchesPath(input, '/api/files')) {
        return new Response(JSON.stringify(makeUploadResponse('pasted.txt', 'file-1')), { status: 200 })
      }
      return new Response(null, { status: 404 })
    })
  })

  afterEach(() => { vi.restoreAllMocks() })

  const fileUploadCount = () =>
    fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) => urlMatchesPath(input, '/api/files')).length

  function stallFileUpload() {
    let resolveUpload!: (value: Response) => void
    const uploadPromise = new Promise<Response>((resolve) => { resolveUpload = resolve })
    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = urlFromFetchInput(input)
      if (urlMatchesPath(input, '/api/files')) return uploadPromise
      const r = defaultFetchResponse(url)
      if (r) return r
      return new Response(null, { status: 404 })
    })
    return () => resolveUpload(new Response(JSON.stringify(makeUploadResponse('first.txt', 'file-1')), { status: 200 }))
  }

  describe('paste handling', () => {
    it('uploads pasted files via POST with a FormData body', async () => {
      renderConverter()
      pasteFiles([new File(['hello world'], 'pasted.txt', { type: 'text/plain' })])

      await screen.findByText('pasted.txt')
      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) => urlMatchesPath(input, '/api/files'))
      expect(fileCalls).toHaveLength(1)
      const [, init] = fileCalls[0]
      expect(init?.method).toBe('POST')
      expect(init?.body).toBeInstanceOf(FormData)
    })

    it('uploads screenshot-style image blobs surfaced only via clipboard.items', async () => {
      renderConverter()
      pasteItems([new File([new Uint8Array([1, 2, 3, 4])], 'image.png', { type: 'image/png' })])

      await screen.findByText('pasted.txt')
      expect(fileUploadCount()).toBe(1)
    })

    it('de-duplicates when the same file appears in both clipboard.files and clipboard.items', async () => {
      renderConverter()
      const file = new File(['hello world'], 'shared.txt', { type: 'text/plain' })
      dispatchPaste(createDataTransfer([file], '', { populateItemsFromFiles: true }))

      await screen.findByText('pasted.txt')
      expect(fileUploadCount()).toBe(1)
    })

    it('ignores empty and text-only pastes (no file or URL upload)', async () => {
      renderConverter()
      pasteFiles([])
      pasteText('https://example.com/file.txt')

      expect(fileUploadCount()).toBe(0)
      expect(fetchSpy.mock.calls.some(([input]: [RequestInfo | URL]) => urlMatchesPath(input, '/api/files/url'))).toBe(false)
    })

    it('starts a parallel upload batch when pasted files arrive while an upload is in progress', async () => {
      const resolveUpload = stallFileUpload()
      renderConverter()

      pasteFiles([new File(['first'], 'first.txt', { type: 'text/plain' })])
      pasteFiles([new File(['second'], 'second.txt', { type: 'text/plain' })])

      expect(fileUploadCount()).toBe(2)
      resolveUpload()
    })

    it('shows an upload progress bar while a file is uploading and removes it afterwards', async () => {
      const resolveUpload = stallFileUpload()
      renderConverter()

      pasteFiles([new File(['first'], 'first.txt', { type: 'text/plain' })])

      const bar = await screen.findByRole('progressbar')
      expect(bar.getAttribute('aria-valuenow')).toBe('0')

      resolveUpload()
      await waitFor(() => expect(screen.queryByRole('progressbar')).toBeNull())
    })

    it.each([0, 1])('aggregates overlapping chunked uploads when batch %i finishes first', async (firstToFinish) => {
      vi.spyOn(api, 'getUploadConfig').mockResolvedValue({ max_chunk_size: 2 })
      const uploads: {
        report: (bytes: number) => void
        finish: () => void
      }[] = []
      vi.spyOn(api, 'chunkedUpload').mockImplementation((file, chunkSize, onProgress) =>
        new Promise((resolve) => {
          uploads.push({
            report: (bytes) => onProgress?.({
              bytesUploaded: bytes,
              totalBytes: file.size,
              chunksUploaded: bytes / chunkSize,
              totalChunks: Math.ceil(file.size / chunkSize),
            }),
            finish: () => resolve(makeUploadResponse(file.name, file.name)),
          })
        }),
      )
      await act(async () => { renderConverter() })
      const percent = () => screen.getByRole('progressbar').getAttribute('aria-valuenow')

      pasteFiles([new File(['1234'], 'first.txt')])
      act(() => uploads[0].report(2))
      expect(percent()).toBe('50')

      pasteFiles([new File(['123456789012'], 'second.txt')])
      expect(percent()).toBe('13')
      expect(screen.getByText('Uploading 2 files...')).toBeTruthy()
      act(() => uploads[1].report(6))
      expect(percent()).toBe('50')

      await act(async () => {
        uploads[firstToFinish].report(firstToFinish === 0 ? 4 : 12)
        uploads[firstToFinish].finish()
      })
      expect(percent()).toBe(firstToFinish === 0 ? '63' : '88')
      expect(screen.getByText('Uploading 1 file...')).toBeTruthy()
      expect(findFileInput().disabled).toBe(true)

      const remaining = 1 - firstToFinish
      act(() => uploads[remaining].report(remaining === 0 ? 4 : 12))
      expect(percent()).toBe('100')
      await act(async () => { uploads[remaining].finish() })
      expect(screen.queryByRole('progressbar')).toBeNull()
      expect(findFileInput().disabled).toBe(false)

      // A later upload starts with fresh totals, not the previous session's bytes.
      pasteFiles([new File(['1234'], 'third.txt')])
      expect(percent()).toBe('0')
      act(() => uploads[2].report(2))
      expect(percent()).toBe('50')
      await act(async () => { uploads[2].finish() })
      expect(screen.queryByRole('progressbar')).toBeNull()
    })

    it('keeps another upload visible when an overlapping batch fails', async () => {
      const responses: ((response: Response) => void)[] = []
      fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
        if (urlMatchesPath(input, '/api/files')) {
          return new Promise<Response>((resolve) => { responses.push(resolve) })
        }
        return defaultFetchResponse(urlFromFetchInput(input)) ?? new Response(null, { status: 404 })
      })
      renderConverter()
      pasteFiles([new File(['first'], 'first.txt')])
      pasteFiles([new File(['second'], 'second.txt')])

      await act(async () => {
        responses[0](new Response(JSON.stringify({ detail: 'Upload failed' }), { status: 500 }))
      })
      expect(screen.getByRole('progressbar')).toBeTruthy()
      expect(screen.getByText('Uploading 1 file...')).toBeTruthy()
      expect(findFileInput().disabled).toBe(true)

      await act(async () => {
        responses[1](new Response(JSON.stringify(makeUploadResponse('second.txt', 'file-2')), { status: 200 }))
      })
      expect(screen.queryByRole('progressbar')).toBeNull()
      expect(findFileInput().disabled).toBe(false)
    })
  })

  describe('drag-and-drop handling', () => {
    it('uploads files dropped onto the drop zone', async () => {
      renderConverter()
      dropFiles(findDropZone(), [new File(['hello world'], 'dropped.txt', { type: 'text/plain' })])

      await screen.findByText('pasted.txt')
      expect(fileUploadCount()).toBe(1)
    })

    it('toggles the drag-over highlight across dragover/dragleave', () => {
      renderConverter()
      const dropZone = findDropZone()

      fireEvent(dropZone, new Event('dragover', { bubbles: true, cancelable: true }))
      expect(dropZone.className).toContain('bg-primary/10')

      fireEvent(dropZone, new Event('dragleave', { bubbles: true }))
      expect(dropZone.className).not.toContain('bg-primary/10')
    })

    it('clears the drag-over highlight after a drop', async () => {
      renderConverter()
      const dropZone = findDropZone()

      fireEvent(dropZone, new Event('dragover', { bubbles: true, cancelable: true }))
      expect(dropZone.className).toContain('bg-primary/10')

      dropFiles(dropZone, [new File(['hello world'], 'dropped.txt', { type: 'text/plain' })])
      await screen.findByText('pasted.txt')
      expect(findDropZone().className).not.toContain('bg-primary/10')
    })
  })

  describe('file-select handling', () => {
    it('uploads files chosen via the hidden file input and clears the input', async () => {
      renderConverter()
      selectFilesViaInput(findFileInput(), [new File(['hello world'], 'chosen.txt', { type: 'text/plain' })])

      await screen.findByText('pasted.txt')
      expect(fileUploadCount()).toBe(1)
      expect(findFileInput().value).toBe('')
    })

    it('ignores an empty file selection', async () => {
      renderConverter()
      selectFilesViaInput(findFileInput(), [])
      expect(fileUploadCount()).toBe(0)
    })
  })
})
