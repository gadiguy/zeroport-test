"""Flag image downloader — sequential via requests with exponential backoff.

Design notes:
- aiohttp is NOT used. Wikimedia's CDN returns HTTP 429 for all aiohttp
  requests regardless of headers, due to TLS/HTTP2 fingerprint detection.
- Concurrency is NOT used. Wikimedia's CDN rate-limits per cache node, and
  parallel requests saturate individual nodes quickly. Sequential downloads
  with exponential backoff on 429 reliably retrieve all images.
- A persistent requests.Session is reused across all downloads for HTTP
  keep-alive efficiency.
"""

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Initial back-off delay (seconds) on HTTP 429; doubles on each retry
_BACKOFF_BASE = 5.0
# Maximum number of retry attempts per image on 429
_MAX_RETRIES = 4
# Polite inter-request pause (seconds) to avoid triggering rate limits
_INTER_REQUEST_DELAY = 0.5

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://en.wikipedia.org/",
}


def slugify(name: str) -> str:
    """Convert a country name to a safe, lowercase filesystem slug."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def flag_filename(country_name: str, flag_url: str) -> str:
    """Build a globally unique filename for a flag image.

    Format: <slug>_<md5_of_url[:8]><original_extension>
    The MD5 of the source URL ensures uniqueness even when two countries
    share similar names or when the URL changes across runs.
    """
    slug = slugify(country_name)
    hash8 = hashlib.md5(flag_url.encode()).hexdigest()[:8]

    # Derive the file extension from the URL path (default to .png)
    parsed_path = urlparse(flag_url).path
    ext = os.path.splitext(parsed_path)[1] or ".png"

    return f"{slug}_{hash8}{ext}"


def _fetch_with_backoff(
    session: requests.Session, url: str, country_name: str
) -> tuple[int, bytes]:
    """GET url, retrying with exponential backoff on HTTP 429.

    Returns (status_code, body_bytes) of the final attempt.
    """
    delay = _BACKOFF_BASE
    for attempt in range(_MAX_RETRIES + 1):
        resp = session.get(url, timeout=15)
        if resp.status_code != 429:
            return resp.status_code, resp.content

        # Rate-limited: log, wait, and retry
        if attempt < _MAX_RETRIES:
            logger.warning(
                "Rate limited for %s (attempt %d/%d) — retrying in %.0fs",
                country_name,
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
            delay *= 2  # exponential backoff

    # All retries exhausted; return the last 429 response
    return 429, b""


def _download_one(
    session: requests.Session, country: dict, dest_dir: Path
) -> None:
    """Download a single flag image and mutate the country dict in-place.

    Sets country['flag_path'] on success.
    Sets country['flag_error'] with a short reason string on failure.
    """
    flag_url = country.get("flag_url", "")
    if not flag_url:
        country["flag_error"] = "no image URL in source"
        return

    filename = flag_filename(country["country_name"], flag_url)
    dest_path = dest_dir / filename

    # Skip the network call if the file was already downloaded in a previous run
    if dest_path.exists():
        country["flag_path"] = str(dest_path)
        return

    try:
        status, data = _fetch_with_backoff(session, flag_url, country["country_name"])

        if status != 200:
            country["flag_error"] = f"HTTP {status}"
            logger.warning(
                "Flag download failed for %s: HTTP %s",
                country["country_name"],
                status,
            )
            return

        # Write image bytes to disk and record the local path
        dest_path.write_bytes(data)
        country["flag_path"] = str(dest_path)

    except requests.Timeout:
        country["flag_error"] = "timed out"
        logger.warning("Flag download timed out for %s", country["country_name"])
    except requests.ConnectionError as exc:
        country["flag_error"] = f"connection error: {exc}"
        logger.warning(
            "Flag download connection error for %s: %s", country["country_name"], exc
        )
    except OSError as exc:
        country["flag_error"] = f"disk error: {exc}"
        logger.warning("Flag write error for %s: %s", country["country_name"], exc)


def download_all_flags(countries: list[dict], flag_images_dir: str) -> None:
    """Download flag images for all countries sequentially.

    Sequential (single-threaded) downloads are used deliberately: Wikimedia's
    CDN rate-limits per cache node, and parallel requests reliably trigger 429s.
    Exponential backoff handles any transient 429s that do occur.

    Creates the destination directory if it does not exist.
    Mutates each country dict in-place, setting 'flag_path' on success
    or 'flag_error' with a short reason string on failure.
    """
    dest_dir = Path(flag_images_dir)

    # Create the images directory (and any parents) if it doesn't exist
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Reuse a single session across all downloads for HTTP keep-alive efficiency
    with requests.Session() as session:
        session.headers.update(_HEADERS)
        for country in countries:
            _download_one(session, country, dest_dir)
            # Polite pause between requests to avoid triggering rate limits
            time.sleep(_INTER_REQUEST_DELAY)
