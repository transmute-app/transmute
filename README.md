<h1>
  <picture height=23px>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/beaker-white.svg" height=23px />
    <source media="(prefers-color-scheme: light)" srcset="assets/brand/images/beaker-black.svg" height=23px />
    <img alt="Transmute logo, a small flask" src="assets/brand/images/beaker-white.svg" height=23px />
  </picture>
  Transmute
</h1>

> [!WARNING]  
> I quite literally *just* launched this project, and it will be under active development for some time - however I would love for you to come along and enjoy the ride! Leave a star
> - Chase

Self-Hosted file converter (WIP!)

## What Does Transmute Replace?
- https://www.freeconvert.com/
- https://cloudconvert.com/
- https://convertio.co/
- https://file-converter.org/


## Status
This project is under heavy development, come back soon to see where it goes!

## Diagrams
Shoutout to draw.io (formerly diagrams.net) I love their software and have always planned out projects using it. Recently I discovered [@hediet](https://github.com/hediet) has a [draw.io vscode extension](https://github.com/hediet/vscode-drawio) so now we have our diagrams stored in git at [docs/diagrams/source](docs/diagrams/source). 

They are also exported to [docs/diagrams/exports](docs/diagrams/source) for easy viewing from the UI.

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
```bash
curl -X GET http://0.0.0.0:3313/files/4a86e7d8-b936-465b-a79d-9c076306d17a -o downloaded_file.png
```
