# Planning
This is just my own running document of things I think I need to do so I don't lose track between work sessions

*Shouldn't you use GitHub projects, or issues?* Wouldn't you like to know weatherboy
## Next Steps
- sqlite db for file metadata (og extension, og filename, uuid, storage path, checksum, size etc.)
```
# For sure
id (uuid, pk)
storage_path (string)
original_filename (string)
media_type (string)        # mime type
extension (string)
size_bytes (int)
checksum (string)          # could be used in future for deduplication / caching?
created_at (timestamp)

# Maybe the following?
width (int)         # images/video
height (int)
duration (float)    # media
codec (string)
pages (int)         # pdf
metadata_json (json) # extensibility
```
- sqlite db for job metadata
```
id (uuid)
converter_id
status
progress
params_json
created_at
started_at
finished_at
error
```
- sqlite db for job / file relationships
```
job_id
file_id
```
- Mime detection using python-magic? Fallback to extension, allows uploading of extensionless files
- Full file handling module including the above
- Some db modules to work with the sqlite dbs mentioned above. Abstracted enough that it would be easy to expand to postgres or something else if needed in the future.