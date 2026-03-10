"""Fetch and parse the Wikipedia population table."""

import re
import requests
from bs4 import BeautifulSoup


def fetch_html(url: str) -> str:
    """Perform an HTTP GET and return the response body as text.

    Raises EnvironmentError if url is empty, RuntimeError on non-200 status.
    """
    if not url:
        raise EnvironmentError(
            "TARGET_URL is not set. Add it to your .env file."
        )

    # Request with a browser-like User-Agent to avoid Wikipedia bot blocks
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; country-population-scraper/1.0)"
        )
    }
    response = requests.get(url, headers=headers, timeout=10)

    # Surface HTTP errors as a descriptive RuntimeError
    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code} fetching {url}. "
            "Check TARGET_URL and network connectivity."
        )

    return response.text


def _clean_population(text: str) -> int:
    """Strip commas, footnote markers, and whitespace then cast to int."""
    # Remove anything that isn't a digit or comma, then strip commas
    digits = re.sub(r"[^\d,]", "", text).replace(",", "")
    return int(digits)


def _resolve_flag_url(src: str) -> str:
    """Convert a protocol-relative or relative Wikipedia image src to https."""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return "https://en.m.wikipedia.org" + src
    return src


def parse_countries(html: str) -> list[dict]:
    """Parse the Wikipedia population wikitable into a list of country dicts.

    Each dict has keys: country_name, population, date_of_data,
    flag_url, flag_path (initially None).

    Raises ValueError if no wikitable is found in the HTML.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find the first sortable wikitable on the page
    table = soup.find("table", class_="wikitable")
    if table is None:
        raise ValueError(
            "No wikitable found in the fetched HTML. "
            "The page structure may have changed."
        )

    countries: list[dict] = []

    # Iterate over every data row (skip the header row)
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])

        # Header rows use <th> exclusively — skip them
        if not cells or all(c.name == "th" for c in cells):
            continue

        # Actual Wikipedia table columns:
        # 0: Location (flag img + country name)  1: Population  2: % world  3: Date  4: Source  5: Notes
        # Require at least 4 cells (need indices 0, 1, 3)
        if len(cells) < 4:
            continue

        # --- Extract flag image URL from the location cell (index 0) ---
        # Actual column layout: 0=Location(flag+name) 1=Population 2=% 3=Date 4=Source 5=Notes
        country_cell = cells[0]
        img = country_cell.find("img")
        flag_url: str = ""
        if img and img.get("src"):
            flag_url = _resolve_flag_url(img["src"])

        # --- Extract country name: the <a> tag that contains text, not the flag link ---
        # Cell 0 has two <a> tags: first wraps the flag <img>, second has the country text
        name_tag = next(
            (a for a in country_cell.find_all("a") if not a.find("img")),
            None,
        )
        if name_tag is None:
            continue
        country_name = name_tag.get_text(strip=True)
        if not country_name:
            continue

        # --- Extract population from cell index 1 ---
        try:
            population = _clean_population(cells[1].get_text())
        except ValueError:
            # Skip rows where population cannot be parsed (e.g. sub-totals)
            continue

        # --- Extract date string from cell index 3 ---
        date_of_data = cells[3].get_text(strip=True)

        countries.append(
            {
                "country_name": country_name,
                "population": population,
                "date_of_data": date_of_data,
                "flag_url": flag_url,
                "flag_path": None,
            }
        )

    return countries
