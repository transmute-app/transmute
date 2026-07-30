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

function findDropZone() {
  return screen.getByTestId('drop-zone')
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

describe('Converter paste handling', () => {
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
