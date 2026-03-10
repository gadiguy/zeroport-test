"""E2E benchmark: compare flag download times at concurrency levels 1–5.

Makes real network requests to Wikipedia. Run with:
    python -m pytest tests/test_e2e_download.py -v -s

Each concurrency level downloads the same 20 flags into a fresh temp directory
so no cached files skew the results. Results are printed as a summary table.
"""

import copy
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import fetch_html, parse_countries
from flags import _fetch_with_backoff, flag_filename, _HEADERS, _BACKOFF_BASE, _MAX_RETRIES

TARGET_URL = (
    "https://en.m.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population"
)
NUM_FLAGS = 20
CONCURRENCY_LEVELS = [1, 2, 3, 4, 5]

# Inter-request pause per worker (seconds). With N workers each sleeping this
# long between requests, the effective global rate is N / INTER_REQUEST_DELAY
# requests-per-second. Keep it conservative to avoid 429s.
_INTER_REQUEST_DELAY = 0.5


def _download_one_timed(
    session: requests.Session, country: dict, dest_dir: Path
) -> dict:
    """Download a single flag, returning a result dict with timing info."""
    flag_url = country["flag_url"]
    filename = flag_filename(country["country_name"], flag_url)
    dest_path = dest_dir / filename

    t0 = time.perf_counter()
    try:
        status, data = _fetch_with_backoff(session, flag_url, country["country_name"])
        elapsed = time.perf_counter() - t0
        if status == 200:
            dest_path.write_bytes(data)
            return {"name": country["country_name"], "status": "ok", "elapsed": elapsed}
        else:
            return {
                "name": country["country_name"],
                "status": f"HTTP {status}",
                "elapsed": elapsed,
            }
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {"name": country["country_name"], "status": f"error: {exc}", "elapsed": elapsed}


def _run_concurrent(countries: list[dict], dest_dir: Path, workers: int) -> list[dict]:
    """Download all flags at the given concurrency level, returning per-flag results."""
    results = []

    def task(country):
        # Each thread gets its own session to avoid sharing connection state
        with requests.Session() as session:
            session.headers.update(_HEADERS)
            result = _download_one_timed(session, country, dest_dir)
            time.sleep(_INTER_REQUEST_DELAY)
            return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, c): c for c in countries}
        for future in as_completed(futures):
            results.append(future.result())

    return results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def countries_20():
    """Fetch and return the first 20 countries with flag URLs from Wikipedia."""
    print(f"\nFetching Wikipedia page: {TARGET_URL}")
    html = fetch_html(TARGET_URL)
    all_countries = parse_countries(html)
    # Keep only entries that have a flag URL
    with_flags = [c for c in all_countries if c.get("flag_url")][:NUM_FLAGS]
    assert len(with_flags) == NUM_FLAGS, (
        f"Expected {NUM_FLAGS} countries with flags, got {len(with_flags)}"
    )
    print(f"Loaded {len(with_flags)} countries.")
    return with_flags


# ---------------------------------------------------------------------------
# Benchmark test
# ---------------------------------------------------------------------------

# Accumulate results across parametrize runs so we can print a summary
_benchmark_results: list[dict] = []


@pytest.mark.parametrize("workers", CONCURRENCY_LEVELS)
def test_download_speed(countries_20, workers, tmp_path):
    """Download {NUM_FLAGS} flags at `workers` concurrency and record wall time."""
    # Deep-copy so each run starts with clean country dicts
    countries = copy.deepcopy(countries_20)
    dest_dir = tmp_path / f"flags_w{workers}"
    dest_dir.mkdir()

    print(f"\n[workers={workers}] Starting download of {NUM_FLAGS} flags …")
    wall_start = time.perf_counter()
    results = _run_concurrent(countries, dest_dir, workers)
    wall_elapsed = time.perf_counter() - wall_start

    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] != "ok"]

    print(f"[workers={workers}] Done in {wall_elapsed:.1f}s — "
          f"{len(ok)} ok, {len(failed)} failed")
    for r in failed:
        print(f"  FAILED  {r['name']}: {r['status']}")

    _benchmark_results.append({
        "workers": workers,
        "wall_s": wall_elapsed,
        "ok": len(ok),
        "failed": len(failed),
    })

    # If this is the last concurrency level, print the summary table
    if workers == CONCURRENCY_LEVELS[-1]:
        _print_summary()

    # Soft assertion: at least 80% of downloads must succeed
    assert len(ok) >= NUM_FLAGS * 0.8, (
        f"Too many failures at workers={workers}: {len(failed)}/{NUM_FLAGS}"
    )


def _print_summary():
    sorted_results = sorted(_benchmark_results, key=lambda r: r["workers"])
    best = min(sorted_results, key=lambda r: r["wall_s"])

    print("\n" + "=" * 55)
    print(f"{'Workers':>8}  {'Time (s)':>10}  {'OK':>5}  {'Failed':>7}  {'':}")
    print("-" * 55)
    for r in sorted_results:
        marker = " ← fastest" if r["workers"] == best["workers"] else ""
        print(
            f"{r['workers']:>8}  {r['wall_s']:>10.1f}  {r['ok']:>5}  {r['failed']:>7}{marker}"
        )
    print("=" * 55)
    print(f"Optimal concurrency: {best['workers']} worker(s) "
          f"({best['wall_s']:.1f}s for {NUM_FLAGS} flags)\n")
