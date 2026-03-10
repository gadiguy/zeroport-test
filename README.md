# Country Population Scraper

A Python CLI tool that fetches the Wikipedia [List of countries and dependencies by population](https://en.m.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population) table, downloads country flag images asynchronously, and outputs the results to stdout or as a styled HTML file.

## Features

- Scrapes the live Wikipedia population table
- Downloads flag images concurrently (async, non-blocking)
- Globally unique flag filenames using country slug + MD5 of source URL
- Outputs a sorted, fixed-width text table to stdout
- Optionally writes a styled HTML table with inline flag images
- Configurable via environment variables (`.env`)
- Filterable by minimum population via CLI argument

## Requirements

- Python 3.11+
- pip

## Setup

```bash
git clone <repo-url>
cd zeroport-test

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

## Configuration

Edit `.env` to override defaults:

| Variable | Description | Default |
| --- | --- | --- |
| `TARGET_URL` | Wikipedia population table URL | `https://en.m.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population` |
| `FLAG_IMAGES_DIR` | Directory to store flag image files | `./flag_images` |

## Usage

```bash
# Print table to stdout, sorted by population descending
python main.py

# Filter to countries with population >= 50 million
python main.py --min_population 50000000

# Write output as an HTML file
python main.py --html_output output.html

# Combine both options
python main.py --min_population 10000000 --html_output output.html
```

### CLI Arguments

| Argument            | Type  | Description                                               |
|---------------------|-------|-----------------------------------------------------------|
| `--min_population`  | `int` | Only include countries with population >= this value      |
| `--html_output`     | `str` | Write HTML output to this file path instead of stdout     |

### Console Output Example

```
Country                                   Population       Date of Data          Flag Path
------------------------------------------------------------------------------------------
India                                     1,441,719,852    1 Mar 2025            ./flag_images/india_3a2f1b4c.png
China                                     1,408,280,000    31 Dec 2024           ./flag_images/china_7e9d2c1a.png
...
```

### HTML Output

A self-contained HTML file with a styled table, including flag thumbnails. Open it in any browser.

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
├── flag_images/       # Downloaded flag images (auto-created at runtime)
├── .env               # Environment variables (not committed to git)
├── .env.example       # Template for required environment variables
├── requirements.txt   # Pinned dependencies
└── CLAUDE.md          # Project spec and AI workflow instructions
```

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocked HTTP responses — no real network calls are made.

## Code Style

```bash
black .
ruff check .
```
