import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import Files from './Files'

function renderFiles() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter>
        <Files />
      </MemoryRouter>
    </I18nextProvider>,
  )
}

function urlOf(input: RequestInfo | URL): URL {
  const raw = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
  return new URL(raw, 'http://localhost')
}

function makeFile(n: number) {
  return {
    id: `file-${n}`,
    original_filename: `file-${n}.png`,
    media_type: 'png',
    extension: '.png',
    size_bytes: 1024 * n,
    created_at: '2026-03-20T12:00:00Z',
    compatible_formats: {},
  }
}

/** A fake GET /api/files page the way the backend would return it. */
function pageResponse(files: ReturnType<typeof makeFile>[], page: number, totalPages: number, totalItems: number) {
  return new Response(
    JSON.stringify({
      files,
      pagination: {
        total_items: totalItems,
        total_pages: totalPages,
        current_page: page,
        limit: 20,
        has_next: page < totalPages,
        has_prev: page > 1,
      },
    }),
    { status: 200 },
  )
}

describe('Files page pagination', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>
  const listCalls = () =>
    fetchSpy.mock.calls
      .map(([input]: [RequestInfo | URL]) => urlOf(input))
      .filter((u: URL) => u.pathname === '/api/files')

  beforeEach(async () => {
    await i18n.changeLanguage('en')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  /** Three pages of one file each, so each page is easy to recognise. */
  function threePages() {
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async (input) => {
      const url = urlOf(input)
      const page = Number(url.searchParams.get('page') ?? '1')
      return pageResponse([makeFile(page)], page, 3, 3)
    })
  }

  it('asks for the first page, newest first, with the page size', async () => {
    threePages()
    renderFiles()

    expect(await screen.findByText('file-1.png')).toBeInTheDocument()
    const first = listCalls()[0]
    expect(first.searchParams.get('page')).toBe('1')
    expect(first.searchParams.get('limit')).toBe('20')
    expect(first.searchParams.get('sort')).toBe('date')
    expect(first.searchParams.get('order')).toBe('desc')
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  })

  it('moves to the next and previous page', async () => {
    threePages()
    renderFiles()
    await screen.findByText('file-1.png')

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('file-2.png')).toBeInTheDocument()
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(listCalls().at(-1)!.searchParams.get('page')).toBe('2')

    fireEvent.click(screen.getByRole('button', { name: /previous/i }))
    expect(await screen.findByText('file-1.png')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  })

  it('disables Previous on the first page and Next on the last', async () => {
    threePages()
    renderFiles()
    await screen.findByText('file-1.png')
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText('file-2.png')
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText('file-3.png')

    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /previous/i })).toBeEnabled()
  })

  it('shows no pagination controls when everything fits on one page', async () => {
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async () => pageResponse([makeFile(1)], 1, 1, 1))
    renderFiles()

    await screen.findByText('file-1.png')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('sorts on the server and goes back to page 1 when a header is clicked', async () => {
    threePages()
    renderFiles()
    await screen.findByText('file-1.png')
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText('file-2.png')

    fireEvent.click(screen.getByRole('button', { name: /filename/i }))

    await waitFor(() => {
      const last = listCalls().at(-1)!
      expect(last.searchParams.get('sort')).toBe('filename')
      expect(last.searchParams.get('order')).toBe('asc')
      expect(last.searchParams.get('page')).toBe('1')
    })
  })

  it('clears the selection when the page changes', async () => {
    threePages()
    renderFiles()
    await screen.findByText('file-1.png')
    fireEvent.click(screen.getAllByRole('button', { name: 'Select' })[0])
    expect(screen.getByRole('button', { name: /delete 1 file/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText('file-2.png')

    expect(screen.queryByRole('button', { name: /delete 1 file/i })).not.toBeInTheDocument()
  })

  it('steps back a page when deleting the last file on the last page', async () => {
    // Page 2 holds one file. Once it is deleted the server has only one page.
    let deleted = false
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async (input, init) => {
      const url = urlOf(input)
      if (init?.method === 'DELETE') {
        deleted = true
        return new Response(JSON.stringify({ message: 'ok' }), { status: 200 })
      }
      const page = Number(url.searchParams.get('page') ?? '1')
      if (deleted) {
        return page === 1
          ? pageResponse([makeFile(1)], 1, 1, 1)
          : pageResponse([], page, 1, 1) // past the end, as the backend answers
      }
      return page === 1
        ? pageResponse([makeFile(1)], 1, 2, 2)
        : pageResponse([makeFile(2)], 2, 2, 2)
    })
    renderFiles()
    await screen.findByText('file-1.png')
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText('file-2.png')

    fireEvent.click(screen.getByTitle('Delete'))

    await waitFor(() => expect(listCalls().at(-1)!.searchParams.get('page')).toBe('1'))
    expect(await screen.findByText('file-1.png')).toBeInTheDocument()
    expect(screen.queryByText('file-2.png')).not.toBeInTheDocument()
  })

  it('refetches the page after a delete so the next file fills the gap', async () => {
    let deleted = false
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async (_input, init) => {
      if (init?.method === 'DELETE') {
        deleted = true
        return new Response(JSON.stringify({ message: 'ok' }), { status: 200 })
      }
      return deleted
        ? pageResponse([makeFile(2), makeFile(3)], 1, 1, 2)
        : pageResponse([makeFile(1), makeFile(2)], 1, 2, 3)
    })
    renderFiles()
    await screen.findByText('file-1.png')

    fireEvent.click(screen.getAllByTitle('Delete')[0])

    expect(await screen.findByText('file-3.png')).toBeInTheDocument()
    expect(screen.queryByText('file-1.png')).not.toBeInTheDocument()
  })

  it('ignores a slow response that arrives after a newer request', async () => {
    // Click Next (page 2 request hangs), then change the sort (a newer request).
    // Answer the newer one first and the page-2 one last: the late page-2 answer
    // must not overwrite what the newest request returned.
    const pending: { url: URL; resolve: (r: Response) => void }[] = []
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation((input) => {
      const url = urlOf(input)
      if (url.searchParams.get('page') === '1' && !url.searchParams.get('sort')?.startsWith('f')) {
        return Promise.resolve(pageResponse([makeFile(1)], 1, 3, 3))
      }
      return new Promise<Response>((resolve) => pending.push({ url, resolve }))
    })
    renderFiles()
    await screen.findByText('file-1.png')

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(pending).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: /filename/i }))
    await waitFor(() => expect(pending).toHaveLength(2))

    const [pageTwoRequest, sortRequest] = pending
    expect(pageTwoRequest.url.searchParams.get('page')).toBe('2')
    expect(sortRequest.url.searchParams.get('sort')).toBe('filename')

    sortRequest.resolve(pageResponse([makeFile(9)], 1, 3, 3))
    expect(await screen.findByText('file-9.png')).toBeInTheDocument()

    pageTwoRequest.resolve(pageResponse([makeFile(2)], 2, 3, 3))
    await new Promise(resolve => setTimeout(resolve, 50))

    expect(screen.getByText('file-9.png')).toBeInTheDocument()
    expect(screen.queryByText('file-2.png')).not.toBeInTheDocument()
  })

  it('shows an error when a page fails to load', async () => {
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async () => new Response('', { status: 500 }))
    renderFiles()

    expect(await screen.findByText('Failed to fetch files')).toBeInTheDocument()
  })

  it('shows the empty message when there are no files', async () => {
    fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async () => pageResponse([], 1, 0, 0))
    renderFiles()

    expect(await screen.findByText('No uploaded files yet.')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})
