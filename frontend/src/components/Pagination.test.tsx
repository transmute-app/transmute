import { fireEvent, render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import Pagination from './Pagination'

function renderPagination(props: Partial<React.ComponentProps<typeof Pagination>> = {}) {
  const onPageChange = vi.fn()
  render(
    <I18nextProvider i18n={i18n}>
      <Pagination page={2} totalPages={5} onPageChange={onPageChange} {...props} />
    </I18nextProvider>,
  )
  return onPageChange
}

describe('Pagination', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
  })

  it('renders nothing for a single page or none', () => {
    renderPagination({ page: 1, totalPages: 1 })
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('renders nothing when there are no pages', () => {
    renderPagination({ page: 1, totalPages: 0 })
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('shows where you are', () => {
    renderPagination()
    expect(screen.getByText('Page 2 of 5')).toBeInTheDocument()
  })

  it('asks for the previous and next page', () => {
    const onPageChange = renderPagination()

    fireEvent.click(screen.getByRole('button', { name: /previous/i }))
    expect(onPageChange).toHaveBeenLastCalledWith(1)

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(onPageChange).toHaveBeenLastCalledWith(3)
  })

  it('disables Previous on the first page and Next on the last', () => {
    renderPagination({ page: 1 })
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeEnabled()
  })

  it('disables Next on the last page', () => {
    renderPagination({ page: 5 })
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /previous/i })).toBeEnabled()
  })

  it('disables both buttons while disabled', () => {
    const onPageChange = renderPagination({ disabled: true })

    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(onPageChange).not.toHaveBeenCalled()
  })

  it('is labelled for assistive technology in the current language', async () => {
    await i18n.changeLanguage('de')
    renderPagination()
    expect(screen.getByRole('navigation', { name: 'Seitennavigation' })).toBeInTheDocument()
    expect(screen.getByText('Seite 2 von 5')).toBeInTheDocument()
    await i18n.changeLanguage('en')
  })
})
