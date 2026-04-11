import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { FaChevronDown, FaSearch } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'

interface FormatDropdownProps {
  value: string
  formats: string[]
  onChange: (format: string) => void
  title?: string
  placeholder?: string
  disabled?: boolean
  triggerClassName?: string
  presorted?: boolean
}

function FormatDropdown({
  value,
  formats,
  onChange,
  title,
  placeholder = 'Select...',
  disabled = false,
  triggerClassName = '',
  presorted = false,
}: FormatDropdownProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const { t } = useTranslation()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const [highlightIndex, setHighlightIndex] = useState(-1)
  const [positioned, setPositioned] = useState(false)

  const sorted = useMemo(() => presorted ? formats : [...formats].sort(), [formats, presorted])

  const filtered = useMemo(() =>
    sorted.filter(f => f.toLowerCase().includes(search.toLowerCase())),
    [sorted, search]
  )

  const applyPosition = useCallback(() => {
    if (!triggerRef.current || !panelRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    // getBoundingClientRect is relative to the visual viewport, but
    // position:fixed is relative to the layout viewport. On mobile with
    // the keyboard open these diverge — offset to compensate.
    const vvTop = window.visualViewport?.offsetTop ?? 0
    const vvLeft = window.visualViewport?.offsetLeft ?? 0
    const top = rect.top + vvTop
    const bottom = rect.bottom + vvTop
    const left = rect.left + vvLeft
    const spaceBelow = window.innerHeight - bottom
    const dropUp = spaceBelow < 220
    const panel = panelRef.current
    panel.style.left = `${left}px`
    panel.style.width = `${Math.max(rect.width, 160)}px`
    if (dropUp) {
      panel.style.top = ''
      panel.style.bottom = `${window.innerHeight - top + 4}px`
    } else {
      panel.style.bottom = ''
      panel.style.top = `${bottom + 4}px`
    }
  }, [])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      const target = e.target as Node
      if (triggerRef.current?.contains(target)) return
      if (panelRef.current?.contains(target)) return
      setOpen(false)
      setSearch('')
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Position & focus when opened
  useEffect(() => {
    if (open) {
      // Defer until portal is mounted so panelRef is available
      requestAnimationFrame(() => {
        applyPosition()
        setPositioned(true)
        // Skip auto-focus on touch devices to avoid virtual keyboard covering the dropdown
        const isTouch = window.matchMedia('(pointer: coarse)').matches
        if (!isTouch) searchRef.current?.focus()
      })
      setHighlightIndex(-1)
    } else {
      setPositioned(false)
    }
  }, [open, applyPosition])

  // Reposition on scroll/resize/visual viewport change while open
  useEffect(() => {
    if (!open) return
    const update = () => applyPosition()
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    // visualViewport fires resize when mobile keyboard opens/closes
    window.visualViewport?.addEventListener('resize', update)
    window.visualViewport?.addEventListener('scroll', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
      window.visualViewport?.removeEventListener('resize', update)
      window.visualViewport?.removeEventListener('scroll', update)
    }
  }, [open, applyPosition])

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIndex < 0 || !listRef.current) return
    const items = listRef.current.children
    if (items[highlightIndex]) {
      (items[highlightIndex] as HTMLElement).scrollIntoView({ block: 'nearest' })
    }
  }, [highlightIndex])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIndex(prev => Math.min(prev + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (highlightIndex >= 0 && highlightIndex < filtered.length) {
        onChange(filtered[highlightIndex])
        setOpen(false)
        setSearch('')
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      setOpen(false)
      setSearch('')
    }
  }

  const handleSelect = (format: string) => {
    onChange(format)
    setOpen(false)
    setSearch('')
  }

  const displayValue = value || placeholder

  const panel = open && createPortal(
    <div
      ref={panelRef}
      className="fixed z-[9999] bg-surface-light border border-surface-dark rounded-lg shadow-xl overflow-hidden"
      style={{
        opacity: positioned ? 1 : 0,
        pointerEvents: positioned ? 'auto' : 'none',
      }}
    >
      {/* Search input */}
      <div className="p-1.5 border-b border-surface-dark">
        <div className="flex items-center gap-1.5 bg-surface-dark rounded px-2 py-1">
          <FaSearch className="text-[0.6rem] text-text-muted flex-shrink-0" />
          <input
            ref={searchRef}
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setHighlightIndex(0) }}
            onKeyDown={handleKeyDown}
            className="bg-transparent text-[16px] sm:text-xs text-text placeholder-text-muted/50 outline-none w-full font-mono"
            placeholder={t('dropdown.search')}
          />
        </div>
      </div>

      {/* Options list */}
      <div ref={listRef} className="max-h-[180px] overflow-y-auto py-1 scrollbar-thin">
        {filtered.length === 0 ? (
          <div className="px-3 py-2 text-xs text-text-muted italic">{t('dropdown.noMatches')}</div>
        ) : (
          filtered.map((format, i) => (
            <button
              key={format}
              type="button"
              onClick={() => handleSelect(format)}
              className={`w-full text-left px-3 py-1.5 text-xs font-mono uppercase transition duration-100 ${
                format === value
                  ? 'text-primary bg-primary/15'
                  : i === highlightIndex
                    ? 'text-text bg-surface-dark'
                    : 'text-text-muted hover:text-text hover:bg-surface-dark/50'
              }`}
            >
              {format}
            </button>
          ))
        )}
      </div>
    </div>,
    document.body
  )

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => {
          if (!disabled) setOpen(prev => !prev)
        }}
        disabled={disabled}
        className={`flex items-center justify-between gap-1.5 text-xs font-mono uppercase bg-primary/20 px-2 py-0.5 rounded text-primary hover:bg-primary/30 transition duration-200 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} ${triggerClassName}`}
        title={title}
      >
        <span className={value ? '' : 'text-text-muted'}>{displayValue}</span>
        <FaChevronDown className={`text-[0.5rem] transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      {panel}
    </>
  )
}

export default FormatDropdown
