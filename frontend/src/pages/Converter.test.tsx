import { fireEvent, render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import Converter from './Converter'

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

  afterEach(() => { fetchSpy.mockRestore() })

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