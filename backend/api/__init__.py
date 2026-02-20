from fastapi import APIRouter
from .routes import health, files, conversions, jobs, docs
from .deps import get_file_db, get_conversion_db, get_conversion_relations_db

router = APIRouter()

# Include all route modules
router.include_router(health.router)
router.include_router(files.router)
router.include_router(conversions.router)
router.include_router(jobs.router)
router.include_router(docs.router)
