# Country Population Scraper

A Python CLI tool that fetches a Wikipedia population table, downloads country flag images asynchronously, and outputs results to stdout or as an HTML file.

## Tech Stack

- **Python** 3.11+
- **requests** — HTTP requests to fetch the target URL
- **beautifulsoup4** — HTML parsing and table extraction
- **requests.Session** — sequential flag image downloads with exponential backoff
- **python-dotenv** — loading environment variables from `.env`
- **pytest** — unit testing

## Project Structure

```text
zeroport-test/
├── main.py            # Entry point; CLI argument parsing and orchestration
├── scraper.py         # HTML fetching and table parsing logic
├── flags.py           # Async flag image downloader
├── renderer.py        # Console and HTML output formatting
├── tests/
│   ├── test_console.py   # Unit test: console output format
│   └── test_html.py      # Unit test: HTML output format
├── flag_images/       # Downloaded flag images (auto-created at runtime; path configurable via .env)
├── .env               # Environment variables (not committed to git)
├── .env.example       # Template for required environment variables
├── requirements.txt   # Pinned dependencies
└── CLAUDE.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Environment Variables

Defined in `.env` (loaded automatically on startup via `python-dotenv`):

| Variable           | Description                         | Default                                                                             |
|--------------------|-------------------------------------|-------------------------------------------------------------------------------------|
| `TARGET_URL`       | Wikipedia population table URL      | `https://en.m.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population` |
| `FLAG_IMAGES_DIR`  | Directory to store flag image files | `./flag_images`                                                                     |

`.env.example`:

```dotenv
TARGET_URL=https://en.m.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population
FLAG_IMAGES_DIR=./flag_images
```

## Usage

```bash
# Basic — print table to stdout, sorted by population descending
python main.py

# Filter by minimum population
python main.py --min_population 1000000

# Write output as an HTML file
python main.py --html-output output.html

# Combine both flags
python main.py --min_population 5000000 --html-output output.html
```

## CLI Arguments

| Argument          | Type  | Description                                              |
|-------------------|-------|----------------------------------------------------------|
| `--min_population`| `int` | Only include countries with population >= this value     |
| `--html-output`   | `str` | Path to write HTML output file; skips stdout if provided |

## Data Model

Each country entry contains:

| Field           | Description                                              |
|-----------------|----------------------------------------------------------|
| `country_name`  | Name of the country or dependency                        |
| `population`    | Population as an integer                                 |
| `date_of_data`  | Date string as listed in the source table                |
| `flag_url`      | Absolute source URL of the flag image (used for hashing) |
| `flag_path`     | Local file path after download; `None` if download failed|
| `flag_error`    | Short reason string if download failed; absent on success|

- Countries are sorted by `population` descending before output.
- If a country appears more than once in the source table, it is listed multiple times.

## Flag Images

- Downloaded **sequentially** using a single `requests.Session` after table parsing completes.
- **Do not use `aiohttp`** — Wikimedia's CDN returns HTTP 429 for all `aiohttp` requests regardless of headers, due to TLS/HTTP2 fingerprint detection.
- **Do not use concurrent/parallel downloads** — Wikimedia's CDN rate-limits per cache node. Even 2 concurrent requests reliably trigger 429 on that node. Sequential downloads avoid this entirely.
- A **0.5 s inter-request pause** is inserted between each download to stay polite.
- **Exponential backoff on 429**: on a rate-limit response, wait 5 s and retry; if still 429, wait 10 s, then 20 s, then 40 s (4 retries max). This handles transient node-level rate limits that may occur even with sequential downloads.
- Storage directory is set by `FLAG_IMAGES_DIR` in `.env` (default: `./flag_images`); created at runtime if it does not exist.
- Filenames are globally unique and derived by slugifying the country name and appending an 8-character MD5 hex digest of the source image URL: `<slug>_<hash>.<ext>` (e.g. `united_kingdom_a3f2c1d4.png`). This prevents collisions between countries with similar names and between runs against different source URLs.
- Existing files are not re-downloaded (idempotent re-runs).
- If a download ultimately fails after all retries, `flag_path` is left as `None` and `flag_error` is set to a short human-readable reason (e.g. `HTTP 429`, `timed out`, `connection error: ...`). The reason is shown inline in both console and HTML output; the run is never aborted.

## Output Formats

### Console (stdout)

Tabular text output with columns: `Country`, `Population`, `Date of Data`, `Flag Path`.

### HTML (`--html-output`)

A self-contained HTML file containing:

- A styled `<table>` with columns: Country, Population, Date of Data, Flag (inline `<img>` tag referencing the local flag path).
- Written to the path provided by `--html-output`.

## Wikipedia Table Structure

The page uses a `wikitable`-classed table with the following **confirmed** column layout (verified against the live page):

- **col 0 — Location**: Contains `<span class="flagicon">` with a flag `<img>` inside an `<a>`, followed by a separate text `<a>` for the country name. The flag `<a>` has no text; the country name `<a>` has no `<img>`.
- **col 1 — Population**: Comma-formatted integer string (e.g. `1,417,492,000`).
- **col 2 — % of world**: Ignored.
- **col 3 — Date**: Date string as-is (e.g. `1 Jul 2025`).
- **col 4 — Source**: Ignored.
- **col 5 — Notes**: Ignored.

There is **no Rank column**. Flag image `src` values are protocol-relative (`//upload.wikimedia.org/...`) and must be prefixed with `https:`. The first data row is a "World" total row and passes through the parser (it has a valid population but no flag image).

## Error Handling

- If `TARGET_URL` is not set, raise a clear `EnvironmentError` with instructions to set it in `.env`.
- If the HTTP request fails (non-200 status or timeout), print an error message to stderr and exit with code 1.
- If the expected table is not found in the HTML, raise a descriptive `ValueError`.
- Flag download failures are non-fatal: log a warning per failed country and continue.

## Testing

```bash
pytest tests/ -v
```

Two unit tests are required:

1. `test_console.py` — assert that console output matches expected format and data for a mocked HTML response.
2. `test_html.py` — assert that HTML output contains expected tags, country data, and flag `<img>` references for a mocked HTML response.

Use `unittest.mock` / `pytest-mock` to mock HTTP calls; tests must not make real network requests.

## Code Style

- Follow **PEP 8**. Format with `black` (line length 88).
- Lint with `ruff`.
- Every significant block of logic must have an inline comment above it explaining what it does.
- Use type hints on all function signatures.
- No bare `except` clauses; always catch specific exception types.

```bash
black .
ruff check .
```

## Workflow

- Always enter **plan mode** before writing or modifying code.
- Confirm the plan with the user before implementation.
