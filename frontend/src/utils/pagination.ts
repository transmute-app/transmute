export const DEFAULT_PAGE_SIZE = 20

export interface PaginationMetadata {
  total_items: number
  total_pages: number
  current_page: number
  page_size: number
  has_next: boolean
  has_prev: boolean
}

export function withPagination(url: string, page: number, pageSize = DEFAULT_PAGE_SIZE): string {
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}page=${page}&page_size=${pageSize}`
}
