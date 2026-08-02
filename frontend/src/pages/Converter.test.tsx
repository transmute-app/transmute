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

function createDataTransfer(files: File[] = [], text = '') {
  // jsdom does not expose a working global DataTransfer constructor, so build a minimal stub.
  const fileList = [...files]
  const items: { kind: string; type: string; file?: File }[] = []
  const dt = {
    files: Object.assign(fileList, {
      length: fileList.length,
      item(i: number) { return fileList[i] ?? null },
    }) as unknown as FileList,
    items: {
      add(file: File) {
        fileList.push(file)
        items.push({ kind: 'file', type: file.type, file })
        return null
      },
      get length() { return items.length },
    },
    getData(type: string) {
      return type === 'text/plain' ? text : ''
    },
    setData(type: string, value: string) {
      if (type === 'text/plain') text = value
    },
  }
  return dt as unknown as DataTransfer
}

function dispatchPaste(dropZone: HTMLElement, dt: DataTransfer) {
  const event = new Event('paste', { bubbles: true })
  Object.defineProperty(event, 'clipboardData', { value: dt })
  fireEvent(dropZone, event)
}

function pasteFiles(dropZone: HTMLElement, files: File[]) {
  const dt = createDataTransfer(files)
  dispatchPaste(dropZone, dt)
}

function pasteText(dropZone: HTMLElement, text: string) {
  const dt = createDataTransfer([], text)
  dispatchPaste(dropZone, dt)
}

function dispatchDrop(dropZone: HTMLElement, dt: DataTransfer) {
  const event = new Event('drop', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'dataTransfer', { value: dt })
  fireEvent(dropZone, event)
}

function dropFiles(dropZone: HTMLElement, files: File[]) {
  const dt = createDataTransfer(files)
  dispatchDrop(dropZone, dt)
}

function dispatchDragOver(dropZone: HTMLElement) {
  fireEvent(dropZone, new Event('dragover', { bubbles: true, cancelable: true }))
}

function dispatchDragLeave(dropZone: HTMLElement) {
  fireEvent(dropZone, new Event('dragleave', { bubbles: true, cancelable: true }))
}

function selectFilesViaInput(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  Object.defineProperty(input, 'value', {
    value: files.length > 0 ? `C:\\fakepath\\${files[0].name}` : '',
    configurable: true,
    writable: true,
  })
  fireEvent.change(input)
}

function findDropZone() {
  return screen.getByTestId('drop-zone')
}

function findFileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement
}

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

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  describe('paste handling', () => {
    it('uploads files pasted onto the drop zone', async () => {
      renderConverter()

      const file = new File(['hello world'], 'pasted.txt', { type: 'text/plain' })
      pasteFiles(findDropZone(), [file])

      await screen.findByText('pasted.txt')
      expect(screen.getByText('pasted.txt')).toBeInTheDocument()

      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files'),
      )
      expect(fileCalls).toHaveLength(1)

      const [, init] = fileCalls[0]
      expect(init?.method).toBe('POST')
      expect(init?.body).toBeInstanceOf(FormData)
    })

    it('ignores pasted files while an upload is already in progress', async () => {
      let resolveUpload: (value: Response) => void
      const uploadPromise = new Promise<Response>((resolve) => {
        resolveUpload = resolve
      })

      fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
        const url = urlFromFetchInput(input)
        if (urlMatchesPath(input, '/api/files')) return uploadPromise
        const defaultResponse = defaultFetchResponse(url)
        if (defaultResponse) return defaultResponse
        return new Response(null, { status: 404 })
      })

      renderConverter()

      const firstFile = new File(['first'], 'first.txt', { type: 'text/plain' })
      pasteFiles(findDropZone(), [firstFile])

      const secondFile = new File(['second'], 'second.txt', { type: 'text/plain' })
      pasteFiles(findDropZone(), [secondFile])

      const fileCallsBeforeResolve = fetchSpy.mock.calls.filter(
        ([input]: [RequestInfo | URL]) => urlMatchesPath(input, '/api/files'),
      )
      expect(fileCallsBeforeResolve).toHaveLength(1)

      resolveUpload!(new Response(JSON.stringify(makeUploadResponse('first.txt', 'file-1')), { status: 200 }))
    })

    it('ignores an empty paste', async () => {
      renderConverter()
      pasteFiles(findDropZone(), [])

      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files'),
      )
      expect(fileCalls).toHaveLength(0)
    })

    it('ignores pasted plain text in the drop zone', async () => {
      renderConverter()
      pasteText(findDropZone(), 'https://example.com/file.txt')

      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files'),
      )
      const urlCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files/url'),
      )
      expect(fileCalls).toHaveLength(0)
      expect(urlCalls).toHaveLength(0)
    })
  })

  describe('drag-and-drop handling', () => {
    it('uploads files dropped onto the drop zone', async () => {
      renderConverter()

      const file = new File(['hello world'], 'dropped.txt', { type: 'text/plain' })
      dropFiles(findDropZone(), [file])

      await screen.findByText('dropped.txt')
      expect(screen.getByText('dropped.txt')).toBeInTheDocument()

      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files'),
      )
      expect(fileCalls).toHaveLength(1)

      const [, init] = fileCalls[0]
      expect(init?.method).toBe('POST')
      expect(init?.body).toBeInstanceOf(FormData)
    })

    it('enters then exits the drag-over highlight across dragover/dragleave', () => {
      renderConverter()
      const dropZone = findDropZone()

      dispatchDragOver(dropZone)
      expect(dropZone.className).toContain('bg-primary/10')

      dispatchDragLeave(dropZone)
      expect(dropZone.className).not.toContain('bg-primary/10')
    })

    it('clears the drag-over highlight after a drop', async () => {
      renderConverter()
      const dropZone = findDropZone()

      dispatchDragOver(dropZone)
      expect(dropZone.className).toContain('bg-primary/10')

      const file = new File(['hello world'], 'dropped.txt', { type: 'text/plain' })
      dropFiles(dropZone, [file])

      await screen.findByText('dropped.txt')
      expect(dropZone.className).not.toContain('bg-primary/10')
    })

    it('ignores drops while an upload is already in progress', async () => {
      let resolveUpload: (value: Response) => void
      const uploadPromise = new Promise<Response>((resolve) => {
        resolveUpload = resolve
      })

      fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
        const url = urlFromFetchInput(input)
        if (urlMatchesPath(input, '/api/files')) return uploadPromise
        const defaultResponse = defaultFetchResponse(url)
        if (defaultResponse) return defaultResponse
        return new Response(null, { status: 404 })
      })

      renderConverter()

      const firstFile = new File(['first'], 'first.txt', { type: 'text/plain' })
      dropFiles(findDropZone(), [firstFile])

      const secondFile = new File(['second'], 'second.txt', { type: 'text/plain' })
      dropFiles(findDropZone(), [secondFile])

      const fileCallsBeforeResolve = fetchSpy.mock.calls.filter(
        ([input]: [RequestInfo | URL]) => urlMatchesPath(input, '/api/files'),
      )
      expect(fileCallsBeforeResolve).toHaveLength(1)

      resolveUpload!(new Response(JSON.stringify(makeUploadResponse('first.txt', 'file-1')), { status: 200 }))
    })
  })

  describe('file-select handling', () => {
    it('uploads files chosen via the hidden file input', async () => {
      renderConverter()

      const file = new File(['hello world'], 'chosen.txt', { type: 'text/plain' })
      selectFilesViaInput(findFileInput(), [file])

      await screen.findByText('chosen.txt')
      expect(screen.getByText('chosen.txt')).toBeInTheDocument()

      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files'),
      )
      expect(fileCalls).toHaveLength(1)

      const [, init] = fileCalls[0]
      expect(init?.method).toBe('POST')
      expect(init?.body).toBeInstanceOf(FormData)
    })

    it('ignores an empty file selection', async () => {
      renderConverter()
      selectFilesViaInput(findFileInput(), [])

      const fileCalls = fetchSpy.mock.calls.filter(([input]: [RequestInfo | URL]) =>
        urlMatchesPath(input, '/api/files'),
      )
      expect(fileCalls).toHaveLength(0)
    })

    it('clears the input value after a successful selection', async () => {
      renderConverter()
      const input = findFileInput()

      const file = new File(['hello world'], 'chosen.txt', { type: 'text/plain' })
      selectFilesViaInput(input, [file])

      await screen.findByText('chosen.txt')
      expect(input.value).toBe('')
    })
  })
})