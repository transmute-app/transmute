import { useEffect, useState } from 'react'
import { FaGithub, FaExternalLinkAlt, FaBook } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'
import { publicFetch as fetch } from '../utils/api'

const RELEASE_VERSION_PATTERN = /^v\d+\.\d+\.\d+$/
const COMMIT_SHA_PATTERN = /^[0-9a-f]{7}$/i
const GITHUB_API_BASE = 'https://api.github.com/repos/transmute-app/transmute'

type AppInfo = {
  name: string
  version: string
}

type UpdateNotice = {
  version: string
  label: string
  href: string
}

function getVersionHref(version: string): string | null {
  if (version === 'dev') return null
  if (RELEASE_VERSION_PATTERN.test(version)) {
    return `https://github.com/transmute-app/transmute/releases/tag/${version}`
  }
  if (COMMIT_SHA_PATTERN.test(version)) {
    return `https://github.com/transmute-app/transmute/commit/${version}`
  }
  return null
}

async function getUpdateNotice(version: string, signal: AbortSignal): Promise<UpdateNotice | null> {
  if (version === 'dev') return null

  if (RELEASE_VERSION_PATTERN.test(version)) {
    const response = await window.fetch(`${GITHUB_API_BASE}/releases/latest`, { signal })
    if (!response.ok) return null
    const data = await response.json() as { tag_name?: string; html_url?: string }
    if (!data.tag_name || !data.html_url || data.tag_name === version) return null
    return {
      version,
      label: `New release ${data.tag_name}`,
      href: data.html_url,
    }
  }

  if (COMMIT_SHA_PATTERN.test(version)) {
    const response = await window.fetch(`${GITHUB_API_BASE}/compare/${version}...main`, { signal })
    if (!response.ok) return null
    const data = await response.json() as { status?: string; total_commits?: number; html_url?: string }
    if (data.status !== 'ahead' || !data.total_commits || !data.html_url) return null
    return {
      version,
      label: `(${data.total_commits} commits behind)`,
      href: data.html_url,
    }
  }

  return null
}

function Footer() {
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null)
  const [updateNotice, setUpdateNotice] = useState<UpdateNotice | null>(null)
  const { t } = useTranslation()
  const currentVersion = appInfo?.version ?? null
  const versionHref = currentVersion ? getVersionHref(currentVersion) : null
  const visibleUpdateNotice = updateNotice?.version === currentVersion ? updateNotice : null

  useEffect(() => {
    fetch('/api/health/info')
      .then(res => res.json())
      .then(data => setAppInfo(data))
      .catch(() => { }) // Silently fail if API is unavailable
  }, [])

  useEffect(() => {
    if (!currentVersion) return

    const controller = new AbortController()

    getUpdateNotice(currentVersion, controller.signal)
      .then(notice => setUpdateNotice(notice))
      .catch(() => { })

    return () => controller.abort()
  }, [currentVersion])

  return (
    <footer className="mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
        <div className="flex flex-col items-center gap-2">
          <a
            href="https://tally.so/r/EkBb6B"
            target="_blank"
            rel="noopener noreferrer"
            className="text-center text-[11px] leading-none text-text-muted/70 hover:text-text transition-colors"
            title={t('footer.surveyCta')}
          >
            {t('footer.surveyCta')}
          </a>
          <div className="flex flex-wrap items-center justify-center gap-2 text-text-muted text-sm">
            <a href="https://github.com/transmute-app/transmute" target="_blank" rel="noopener noreferrer" className="hover:text-text transition-colors" aria-label="GitHub" title={t('footer.sourceCode')}>
              <FaGithub size={16} />
            </a>
            <span className="text-text-muted/30">|</span>
            <span>
              {appInfo?.name || t('app.name')}
              {appInfo?.version && (
                versionHref ? (
                  <a
                    href={versionHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-2 text-text-muted/60 hover:text-text transition-colors"
                    title={`Version ${appInfo.version}`}
                  >
                    {appInfo.version}
                  </a>
                ) : (
                  <span className="ml-2 text-text-muted/60">{appInfo.version}</span>
                )
              )}
            </span>
            {visibleUpdateNotice && (
              <>
                <span className="text-text-muted/30">|</span>
                <a
                  href={visibleUpdateNotice.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center self-center rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-medium leading-none text-primary-light hover:border-primary/50 hover:bg-primary/15 transition-colors"
                  title={visibleUpdateNotice.label}
                >
                  {visibleUpdateNotice.label}
                </a>
              </>
            )}
            <span className="text-text-muted/30">|</span>
            <a href="/api/docs" className="hover:text-text transition-colors" aria-label={t('footer.apiDocs')} title={t('footer.apiDocs')}>
              <FaBook size={14} />
            </a>
            <span className="text-text-muted/30">|</span>
            <a href="https://transmute.sh" target="_blank" rel="noopener noreferrer" className="hover:text-text transition-colors" aria-label={t('footer.website')} title={t('footer.website')}>
              <FaExternalLinkAlt size={13} />
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer
