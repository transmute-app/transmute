<h1>
  <picture height=25px>
    <source media="(prefers-color-scheme: dark)" srcset="images/beaker-white.svg" height=25px/>
    <source media="(prefers-color-scheme: light)" srcset="images/beaker-black.svg" height=25px/>
    <img alt="Transmute logo, a small flask" src="images/beaker-white.svg" />
  </picture>
  Transmute
</h1>

Self-Hosted file converter (WIP!)

Currently supported file conversions:
- Image to Image (png -> jpg, jpg -> webp, etc.)
- Video to Video (mkv -> mp4, mov -> mkv, etc.)
- Video to Audio (mkv -> mp3, mov -> wav, etc.)
- Audio to Audio (mp3 -> wav, flac -> aac, etc.)

## Status
This project is under heavy development, come back soon to see where it goes!


## API Call Flow
*Just drafting as of now, will likely change I can already see some issues with it*
### Starting a Conversion
1. Upload the file you wish to convert
```bash
curl -X POST "http://localhost:3313/files/" \                                   
  -F "file=@test-files/forest-example.jpg"
```
2. Save the `file_id` for use in the next call
```json
{
  "message":"File uploaded successfully",
  "file_id":"4a86e7d8-b936-465b-a79d-9c076306d17a",
  "filename":"forest-example.jpg",
  "content_type":"image/jpeg",
  "stored_as":"4a86e7d8-b936-465b-a79d-9c076306d17a.jpg",
  "size":199525
}
```
3. Start the conversion
```bash
curl -X POST http://0.0.0.0:3313/conversions/ \
  -d '{"id": "4a86e7d8-b936-465b-a79d-9c076306d17a", "input_format": "jpg", "output_format": "png"}'
```
4. Wait for the job to finish (will use the jobs endpoint? maybe some websocket here would be best instead of polling)
5. Download the converted file once finished