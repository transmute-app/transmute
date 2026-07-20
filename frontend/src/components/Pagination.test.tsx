import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Pagination from './Pagination'
import type { PaginationMetadata } from '../utils/pagination'


const pagination: PaginationMetadata = {
  total_items: 45,
  total_pages: 3,
  current_page: 2,
  page_size: 20,
  has_next: true,
  has_prev: true,
}


describe('Pagination', () => {
  it('navigates to adjacent pages', () => {
    const onPageChange = vi.fn()
    render(<Pagination pagination={pagination} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(onPageChange).toHaveBeenNthCalledWith(1, 1)
    expect(onPageChange).toHaveBeenNthCalledWith(2, 3)
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
  })

  it('does not render for a single page', () => {
    const { container } = render(
      <Pagination
        pagination={{ ...pagination, total_items: 10, total_pages: 1, current_page: 1 }}
        onPageChange={() => {}}
      />,
    )

    expect(container.firstChild).toBeNull()
  })
})
