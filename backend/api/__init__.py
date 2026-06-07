from fastapi import APIRouter
from .routes import health, files, conversions, converters, jobs, docs, settings, default_formats, default_qualities, users, api_keys, oidc, guest, stats, compressions, compression_jobs, default_compression_levels

router = APIRouter()

# Register route modules
router.include_router(health.router)
router.include_router(files.router)
router.include_router(conversions.router)
router.include_router(converters.router)
router.include_router(jobs.router)
router.include_router(compressions.router)
router.include_router(compression_jobs.router)
router.include_router(default_compression_levels.router)
router.include_router(settings.router)
router.include_router(default_formats.router)
router.include_router(default_qualities.router)
router.include_router(users.router)
router.include_router(api_keys.router)
router.include_router(oidc.router)
router.include_router(guest.router)
router.include_router(stats.router)
router.include_router(docs.router)
