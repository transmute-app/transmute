from collections import defaultdict

from fastapi import APIRouter, Depends

from api.deps import get_current_admin_user, get_file_db, get_conversion_db, get_conversion_relations_db, get_compression_db, get_compression_relations_db, get_user_db
from api.schemas import StatsResponse, ErrorResponse
from db import FileDB, ConversionDB, ConversionRelationsDB, CompressionDB, CompressionRelationsDB, UserDB

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "",
    summary="Get stats for all users",
    responses={
        200: {
            "model": StatsResponse,
            "description": "Aggregated stats across all users",
        },
        403: {
            "model": ErrorResponse,
            "description": "Admin privileges required",
        },
    },
)
def get_stats(
    file_db: FileDB = Depends(get_file_db),
    conversion_db: ConversionDB = Depends(get_conversion_db),
    conv_rel_db: ConversionRelationsDB = Depends(get_conversion_relations_db),
    compression_db: CompressionDB = Depends(get_compression_db),
    comp_rel_db: CompressionRelationsDB = Depends(get_compression_relations_db),
    user_db: UserDB = Depends(get_user_db),
    current_user: dict = Depends(get_current_admin_user),
):
    """Return upload, output-file, and storage stats for every user (admin only)."""
    users = user_db.list_users()
    user_lookup = {u["uuid"]: u["username"] for u in users}

    all_files = file_db.list_files()
    all_conversions = conversion_db.list_files()
    all_compressions = compression_db.list_files()
    all_conversion_relations = conv_rel_db.list_relations()
    all_compression_relations = comp_rel_db.list_relations()

    # Per-user accumulators
    files_count: dict[str, int] = defaultdict(int)
    storage: dict[str, int] = defaultdict(int)

    for f in all_files:
        uid = f.get("user_id", "")
        files_count[uid] += 1
        storage[uid] += f.get("size_bytes", 0)

    # "Output files" counts every produced file: conversions and compressions.
    output_files_count: dict[str, int] = defaultdict(int)
    for rel in all_conversion_relations:
        uid = rel.get("user_id", "")
        output_files_count[uid] += 1
    for rel in all_compression_relations:
        uid = rel.get("user_id", "")
        output_files_count[uid] += 1

    for c in all_conversions:
        uid = c.get("user_id", "")
        storage[uid] += c.get("size_bytes", 0)

    for c in all_compressions:
        uid = c.get("user_id", "")
        storage[uid] += c.get("size_bytes", 0)

    # Build per-user stats for every known user
    user_stats = []
    for uuid, username in user_lookup.items():
        user_stats.append({
            "user_uuid": uuid,
            "username": username,
            "files_uploaded": files_count.get(uuid, 0),
            "output_files": output_files_count.get(uuid, 0),
            "storage_bytes": storage.get(uuid, 0),
        })

    return {
        "total_files_uploaded": sum(files_count.values()),
        "total_output_files": sum(output_files_count.values()),
        "total_storage_bytes": sum(storage.values()),
        "users": user_stats,
    }
