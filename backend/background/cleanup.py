import calendar
import threading
import time

from db import FileDB, SettingsDB
from core import delete_file_and_metadata

def cleanup_logic():
    now = time.time()
    settings_db = SettingsDB()
    ttl_minutes = settings_db.get_settings().get("cleanup_ttl_minutes", 60)
    settings_db.close()
    file_db = FileDB()
    all_files = file_db.list_files()

    for file in all_files:
        created_at_timestamp = file.get('created_at')  # Example: 2026-02-28 19:25:43
        if created_at_timestamp:
            created_at = calendar.timegm(time.strptime(created_at_timestamp, "%Y-%m-%d %H:%M:%S"))
            if now - created_at > ttl_minutes * 60:  # If the file was created more than the TTL seconds ago
                delete_file_and_metadata(file['id'], file_db)

def cleanup_task():
    while True:
        cleanup_logic()
        time.sleep(60) # Sleep for 1 minute

def get_cleanup_thread():
    thread = threading.Thread(target=cleanup_task)
    thread.daemon = True # Allows the main program to exit even if the thread is running
    return thread