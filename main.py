"""Entry point: parse CLI args, orchestrate scraping, downloading, and output."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from flags import download_all_flags
from renderer import render_console, render_html
from scraper import fetch_html, parse_countries

# Load environment variables from .env before reading os.environ
load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def _parse_args() -> argparse.Namespace:
    """Define and parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape Wikipedia population table and output country data."
    )

    # Optional minimum population filter
    parser.add_argument(
        "--min_population",
        type=int,
        default=None,
        metavar="N",
        help="Only include countries with population >= N.",
    )

    # Optional HTML output path; if omitted, output goes to stdout
    parser.add_argument(
        "--html_output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write output as an HTML file to FILE instead of stdout.",
    )

    return parser.parse_args()


def main() -> None:
    """Main orchestration: fetch → parse → filter → sort → download → render."""
    args = _parse_args()

    # Read required environment variables
    target_url = os.environ.get("TARGET_URL", "")
    flag_images_dir = os.environ.get("FLAG_IMAGES_DIR", "./flag_images")

    if not target_url:
        print(
            "Error: TARGET_URL is not set. Add it to your .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Fetch the HTML page from the target URL
    try:
        html = fetch_html(target_url)
    except (RuntimeError, EnvironmentError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Parse the wikitable into a list of country dicts
    try:
        countries = parse_countries(html)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Apply minimum population filter if requested
    if args.min_population is not None:
        countries = [c for c in countries if c["population"] >= args.min_population]

    # Sort by population descending
    countries.sort(key=lambda c: c["population"], reverse=True)

    # Download flag images asynchronously; mutates flag_path in each dict
    download_all_flags(countries, flag_images_dir)

    # Render to HTML file or print to stdout
    if args.html_output:
        render_html(countries, args.html_output)
        print(f"HTML output written to {args.html_output}")
    else:
        print(render_console(countries))


if __name__ == "__main__":
    main()
