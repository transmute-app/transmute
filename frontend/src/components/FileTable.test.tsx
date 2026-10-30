import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import FileTable, { formatFileSize, type FileTableRow } from './FileTable'

describe('formatFileSize', () => {
  it('formats bytes and kilobytes', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(1536)).toBe('1.5 KB')
  })

  it('formats megabytes and larger units', () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(formatFileSize(3 * 1024 * 1024 * 1024)).toBe('3.0 GB')
  })
})

describe('FileTable', () => {
  const rows: FileTableRow[] = [
    {
      id: 'file-1',
      file: {
        id: 'file-1',
        original_filename: 'report.pdf',
        media_type: 'pdf',
        extension: '.pdf',
        size_bytes: 2048,
        created_at: '2026-03-20T12:00:00Z',
      },
    },
  ]

  it('renders nothing when there are no rows', () => {
    const { container } = render(<FileTable rows={[]} />)

    expect(container.firstChild).toBeNull()
  })

  it('renders a basic file row', () => {
    render(<FileTable rows={rows} />)

    expect(screen.getByText('report.pdf')).toBeInTheDocument()
    expect(screen.getByText('pdf')).toBeInTheDocument()
    expect(screen.getAllByText('2.0 KB').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /filename/i })).toBeInTheDocument()
  })

  it('renders the converted filename and conversion size when present', () => {
    render(
      <FileTable
        rows={[
          {
            ...rows[0],
            conversion: {
              id: 'conversion-1',
              original_filename: 'report.pdf',
              media_type: 'docx',
              extension: '.docx',
              size_bytes: 4096,
              created_at: '2026-03-21T09:30:00Z',
            },
          },
        ]}
      />
    )

    expect(screen.getByText('report.docx')).toBeInTheDocument()
    expect(screen.getAllByText('4.0 KB').length).toBeGreaterThan(0)
    expect(screen.getByText('docx')).toBeInTheDocument()
  })

  it('renders quality descriptions only inside the open dropdown', () => {
    render(
      <FileTable
        isPending
        rows={[
          {
            ...rows[0],
            selectedFormat: 'mp4',
            selectedQuality: 'medium',
            onQualityChange: () => {},
            file: {
              ...rows[0].file,
              compatible_formats: {
                mp4: ['low', 'medium', 'high'],
              },
            },
          },
        ]}
      />,
    )

    const lowDescription = 'Smaller file size, fast conversion speed, poor quality'
    const mediumDescription = 'Medium file size, medium conversion speed, decent quality'
    const highDescription = 'Large file size, slow conversion speed, high quality'

    // Descriptions are not visible while the dropdown is closed.
    expect(screen.queryByText(lowDescription)).not.toBeInTheDocument()
    expect(screen.queryByText(mediumDescription)).not.toBeInTheDocument()
    expect(screen.queryByText(highDescription)).not.toBeInTheDocument()

    // Open the quality dropdown via its trigger.
    const trigger = screen.getByTitle('Quality: medium')
    fireEvent.click(trigger)

    expect(screen.getByText(lowDescription)).toBeInTheDocument()
    expect(screen.getByText(mediumDescription)).toBeInTheDocument()
    expect(screen.getByText(highDescription)).toBeInTheDocument()
  })

  describe('sorting', () => {
    const makeRow = (name: string, size: number): FileTableRow => ({
      id: name,
      file: {
        id: name,
        original_filename: name,
        media_type: 'pdf',
        extension: '.pdf',
        size_bytes: size,
        created_at: '2026-03-20T12:00:00Z',
      },
    })
    const unsorted = [makeRow('b.pdf', 20), makeRow('c.pdf', 30), makeRow('a.pdf', 10)]
    const renderedNames = () => screen.getAllByText(/\.pdf$/).map(el => el.textContent)

    it('sorts the rows itself when uncontrolled', () => {
      render(<FileTable rows={unsorted} />)

      fireEvent.click(screen.getByRole('button', { name: /filename/i }))

      expect(renderedNames()).toEqual(['a.pdf', 'b.pdf', 'c.pdf'])
    })

    it('shows rows in the order given and reports clicks when controlled', () => {
      const onSortChange = vi.fn()
      render(
        <FileTable rows={unsorted} sortColumn="size" sortDirection="asc" onSortChange={onSortChange} />,
      )

      // The parent owns the order, so the table must not re-sort.
      expect(renderedNames()).toEqual(['b.pdf', 'c.pdf', 'a.pdf'])

      fireEvent.click(screen.getByRole('button', { name: /filename/i }))
      expect(onSortChange).toHaveBeenLastCalledWith('filename', 'asc')

      // Clicking the column that is already active flips its direction.
      fireEvent.click(screen.getByRole('button', { name: /size/i }))
      expect(onSortChange).toHaveBeenLastCalledWith('size', 'desc')

      // Date is the one column that starts descending.
      fireEvent.click(screen.getByRole('button', { name: /date/i }))
      expect(onSortChange).toHaveBeenLastCalledWith('date', 'desc')

      expect(renderedNames()).toEqual(['b.pdf', 'c.pdf', 'a.pdf'])
    })

    it('marks the controlled column as sorted for assistive technology', () => {
      render(
        <FileTable rows={unsorted} sortColumn="size" sortDirection="desc" onSortChange={() => {}} />,
      )

      const sizeHeader = screen.getByRole('button', { name: /size/i }).closest('th')
      expect(sizeHeader).toHaveAttribute('aria-sort', 'descending')
      const nameHeader = screen.getByRole('button', { name: /filename/i }).closest('th')
      expect(nameHeader).toHaveAttribute('aria-sort', 'none')
    })
  })
})
