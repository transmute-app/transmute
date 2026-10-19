# End-to-end (e2e) tests for web

Browser tests written in plain English for [Kane CLI](https://www.testmuai.com/kane-cli/).

| Test | What it covers |
|---|---|
| `admin_test.md` | Creating the admin account, logging out and logging back in |
| `convert_test.md` | Admin setup, adding a sample CSV by URL, converting it to JSON and finding it in Jobs |

## Run

Start a fresh instance on port 4850:

```bash
docker run -d --name transmute-e2e -p 4850:3313 ghcr.io/transmute-app/transmute:latest
npm install -g @testmuai/kane-cli
kane-cli login
kane-cli testmd run e2e/kane/admin_test.md
kane-cli testmd run e2e/kane/convert_test.md
```

Both tests start from the admin setup page, so recreate the container before each run. `convert_test.md` fetches `assets/samples/csv.csv` from GitHub, so it needs internet access.
