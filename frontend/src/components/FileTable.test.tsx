import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
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
    expect(screen.getByText('4.0 KB')).toBeInTheDocument()
    expect(screen.getByText('docx')).toBeInTheDocument()
  })
})
