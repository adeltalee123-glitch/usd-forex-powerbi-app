# USD Forex Power BI Web App

This is a lightweight web app and API service for serving USD forex historical data to both a browser UI and Power BI.

## Features

- pair catalog endpoint
- forex data API in JSON and CSV
- status endpoint
- browser-based filter UI
- SQLite storage
- seed script with sample daily data
- live Dukascopy provider support
- years selector from `1` to `10`
- granularity options from `1 minute` to `1 day`
- strategy-friendly output with both `bid_*` and `ask_*` columns

## Project Structure

```text
forex_powerbi_app/
  app/
    database.py
    seed_data.py
    server.py
    static/
      index.html
      app.js
      styles.css
  data/
  requirements.txt
```

## Run

From the project root:

```bash
cd /Users/matebook14/Documents/Playground/forex_powerbi_app
python3 -m app.seed_data
python3 -m app.server
```

Then open:

- Website: `http://localhost:8000`
- Pairs API: `http://localhost:8000/api/pairs`
- All USD pairs JSON: `http://localhost:8000/api/forex/usd-pairs?years=1&granularity=1d&source=seed`
- All USD pairs CSV: `http://localhost:8000/api/forex/usd-pairs?years=1&granularity=1d&source=seed&format=csv`

## Power BI

Recommended initial connection:

```text
http://localhost:8000/api/forex/usd-pairs?years=3&granularity=1d&offer_side=BOTH&source=seed&format=csv
```

You can also use:

```text
http://localhost:8000/api/forex/pairs?symbols=EUR/USD,USD/JPY&years=3&granularity=5m&offer_side=BOTH&source=live&format=csv
```

## Deploy To Render

This repo includes [render.yaml](/Users/matebook14/Documents/Playground/forex_powerbi_app/render.yaml) so you can deploy it as a public HTTPS app for Power BI Service.

Steps:

1. Push this folder to a GitHub repo.
2. In Render, choose `New +` -> `Blueprint`.
3. Connect the GitHub repo and deploy the blueprint.
4. Wait for the web service to finish deploying.
5. Open the public URL and verify:
   - `/api/status`
   - `/api/forex/usd-pairs?years=1&granularity=1d&offer_side=BOTH&source=live&format=csv`

Notes:

- The deployed app uses `https://jetta.dukascopy.com` for live data by default.
- `SEED_SAMPLE_DATA_ON_STARTUP=1` is enabled in Render so the sample mode works after deploy.
- Render's free plan uses ephemeral disk, so sample SQLite data may reset on redeploy or restart.

## Power BI Service

Power BI Service cannot reach `127.0.0.1` or `localhost`. Use the public Render HTTPS URL instead.

Recommended pattern:

```text
https://YOUR-RENDER-APP.onrender.com/api/forex/pairs?symbols=USD/HKD&years=5&granularity=1d&offer_side=BOTH&source=live&format=csv
```

Connection guidance:

- If you use `format=csv`, connect from Power BI using a web/CSV-style import.
- If you use `format=json`, connect from Power BI using a web API style import.

## Notes

- `source=seed` works immediately with the local SQLite sample dataset.
- `source=seed` supports the same `1m` to `1d` granularity menu through synthetic intraday expansion.
- `source=live` now defaults to the official Dukascopy widget backend discovered from [config.json](https://widgets.dukascopy.com/config.json): `https://jetta.dukascopy.com`
- `DUKASCOPY_JETTA_BASE` is still supported as an override if you want to point the app at a different Dukascopy environment.
- `DUKASCOPY_JETTA_BASE` may be set either to the widget API root or directly to a `/v1` root. The provider handles both.
- the provider uses the local CA bundle automatically, preferring `/etc/ssl/cert.pem` on macOS-style systems
- if your Python environment still has certificate issues, you can temporarily disable verification:

```bash
export DUKASCOPY_SSL_NO_VERIFY=1
python3 -m app.server
```
- Practical live-mode limits are enforced to keep the API and Power BI usable:
  - `tick`: up to 1 day
  - `1s` to `45s`: up to 7 days
  - `1m` to `3m`: up to 366 days
  - `5m` to `45m`: up to 1826 days
  - `1h` and coarser: up to 10 years
- API output is now strategy-oriented:
  - `bid_open`, `bid_high`, `bid_low`, `bid_close`
  - `ask_open`, `ask_high`, `ask_low`, `ask_close`
  - `spread`, `bid_volume`, `ask_volume`
- Example:

```bash
export DUKASCOPY_JETTA_BASE='https://YOUR_DISCOVERED_DUKASCOPY_BASE'
python3 -m app.server
```
