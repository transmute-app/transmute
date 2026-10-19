---
mode: testing
url: http://localhost:4850/
max_steps: 50
---

# Convert a CSV file to JSON

## Create the admin account
Type "samrivera" as the Username, "Sam Rivera" as the Full name, "sam@example.com" as the Email and "Transmute-Test-2026" as the Password, then click "Create Admin Account".
Verify the workspace shows "Drop files here or click to browse".

## Add a file by URL
Type "https://raw.githubusercontent.com/transmute-app/transmute/main/assets/samples/csv.csv" in the "URL for Transmute to grab" field and click "Add".
Verify "Pending (1)" is shown with the file "csv.csv".

## Convert it to JSON
Click the format button next to "csv.csv", type "json" in the format search box and select "JSON".
Click "Convert 1 File".
Verify "Completed (1)" is shown with the file "csv.json" in JSON format.

## Check the job history
Click "Jobs" in the top navigation.
Verify "csv.json" is listed with the format JSON.
