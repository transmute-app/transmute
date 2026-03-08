import calendar
import threading
import time

from db import FileDB, ConversionDB, ConversionRelationsDB, SettingsDB
from core import delete_file_and_metadata

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
        except Exception as e:
            print(f"Cleanup error: {e}")
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