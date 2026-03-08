from fastapi import APIRouter, Depends

from api.deps import get_current_active_user

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_active_user)])


@router.get("")
def list_jobs():
    return {"jobs": []}
