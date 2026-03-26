import logging
import calendar
import threading
import time

from db import FileDB, ConversionDB, ConversionRelationsDB, SettingsDB, DefaultFormatsDB, UserDB, ApiKeyDB
from core import delete_file_and_metadata


logger = logging.getLogger(__name__)

def file_cleanup_logic(file_db: FileDB, conversion_relations_db: ConversionRelationsDB = None) -> None:
    """Delete files that have exceeded the configured cleanup TTL.

    Reads cleanup settings from the first admin user's configuration.
    Files are cleaned up regardless of user ownership as this is a
    system maintenance task.
    """
    now = time.time()
    settings_db = SettingsDB()
    admin_settings = settings_db.get_admin_cleanup_settings()
    cleanup_enabled = admin_settings["cleanup_enabled"]
    ttl_minutes = admin_settings["cleanup_ttl_minutes"]

    if not cleanup_enabled:
        return

    all_files = file_db.list_files()

    for file in all_files:
        created_at_timestamp = file.get('created_at')  # Example: 2026-02-28 19:25:43
        if created_at_timestamp:
            created_at = calendar.timegm(time.strptime(created_at_timestamp, "%Y-%m-%d %H:%M:%S"))
            if now - created_at > ttl_minutes * 60:  # If the file was created more than the TTL seconds ago
                delete_file_and_metadata(file['id'], file_db)
                if conversion_relations_db:
                    # Additional cleanup logic for conversion relations
                    conversion_relations_db.delete_relation_by_converted(file['id'])

def guest_cleanup_logic() -> None:
    """Delete expired guest users and all their associated data."""
    user_db = UserDB()
    expired_guests = user_db.list_expired_guests()
    if not expired_guests:
        return

    file_db = FileDB()
    conversion_db = ConversionDB()
    conversion_relations_db = ConversionRelationsDB()
    settings_db = SettingsDB()
    default_formats_db = DefaultFormatsDB()
    api_key_db = ApiKeyDB()

    for guest in expired_guests:
        guest_uuid = guest["uuid"]
        api_key_db.delete_all_keys_for_user(guest_uuid)
        for f in file_db.list_files(user_id=guest_uuid):
            delete_file_and_metadata(f["id"], file_db, raise_if_not_found=False)
        for c in conversion_db.list_files(user_id=guest_uuid):
            delete_file_and_metadata(c["id"], conversion_db, raise_if_not_found=False)
            conversion_relations_db.delete_relation_by_converted(c["id"])
        settings_db.delete_settings(guest_uuid)
        default_formats_db.delete_all(guest_uuid)
        user_db.delete_user(guest_uuid)
        logger.info("Deleted expired guest user %s", guest_uuid)


def file_cleanup_task() -> None:
    """Periodically run cleanup logic for uploaded and converted files.

    Runs in an infinite loop, invoking file_cleanup_logic for both uploaded
    files (FileDB) and converted files (ConversionDB / ConversionRelationsDB)
    on each iteration, then sleeps for 60 seconds before repeating.
    """
    while True:
        try:
            file_cleanup_logic(FileDB())
            file_cleanup_logic(ConversionDB(), ConversionRelationsDB())
            guest_cleanup_logic()
        except Exception:
            logger.exception("Cleanup error")
        time.sleep(60) # Sleep for 1 minute

def get_upload_cleanup_thread() -> threading.Thread:
    """Create and return a daemon thread that runs the file cleanup task.

    The returned thread is configured as a daemon so it will not prevent the
    main process from exiting. The caller is responsible for starting the
    thread.

    Returns:
        A daemon Thread targeting file_cleanup_task, ready to be started.
    """
    thread = threading.Thread(target=file_cleanup_task)
    thread.daemon = True # Allows the main program to exit even if the thread is running
    return thread