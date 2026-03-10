"""Unit test: HTML output format and correctness."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

# Minimal wikitable fixture matching actual Wikipedia column layout:
# 0=Location(flag+name)  1=Population  2=%world  3=Date  4=Source  5=Notes
FIXTURE_HTML = """
<html><body>
<table class="wikitable">
  <thead>
    <tr><th>Location</th><th>Population</th><th>%</th><th>Date</th><th>Source</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="flagicon"><a href="/wiki/Alpha"><img src="//upload.wikimedia.org/flag_alpha.png" alt="Alpha"></a></span> <a href="/wiki/Demographics_of_Alpha">Alpha</a></td>
      <td>1,400,000,000</td>
      <td>17.5%</td>
      <td>2023</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td><span class="flagicon"><a href="/wiki/Beta"><img src="//upload.wikimedia.org/flag_beta.png" alt="Beta"></a></span> <a href="/wiki/Demographics_of_Beta">Beta</a></td>
      <td>500,000,000</td>
      <td>6.3%</td>
      <td>2022</td>
      <td></td>
      <td></td>
    </tr>
  </tbody>
</table>
</body></html>
"""


def _build_countries() -> list[dict]:
    """Parse the fixture HTML and inject fake flag paths."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scraper import parse_countries

    countries = parse_countries(FIXTURE_HTML)
    # Inject fake local flag paths (simulating a completed download)
    for c in countries:
        c["flag_path"] = f"/fake/flags/{c['country_name'].lower()}.png"
    return countries


class TestHtmlOutput(unittest.TestCase):
    """Verify that the HTML renderer produces a valid, complete table."""

    def setUp(self):
        """Build the countries list and render HTML once for all tests."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from renderer import render_html

        self.countries = _build_countries()
        self.output_path = "/tmp/test_output.html"

        # Render to a temp file and read it back
        render_html(self.countries, self.output_path)
        self.html_content = Path(self.output_path).read_text(encoding="utf-8")
        self.soup = BeautifulSoup(self.html_content, "lxml")

    def test_html_table_present(self):
        """Output must contain exactly one <table> element."""
        tables = self.soup.find_all("table")
        self.assertEqual(len(tables), 1)

    def test_table_headers(self):
        """Table must have Country, Population, Date of Data, Flag headers."""
        headers = [th.get_text(strip=True) for th in self.soup.find_all("th")]
        self.assertIn("Country", headers)
        self.assertIn("Population", headers)
        self.assertIn("Date of Data", headers)
        self.assertIn("Flag", headers)

    def test_country_names_in_table(self):
        """Both country names must appear as table cell text."""
        cell_texts = [td.get_text(strip=True) for td in self.soup.find_all("td")]
        self.assertTrue(any("Alpha" in t for t in cell_texts))
        self.assertTrue(any("Beta" in t for t in cell_texts))

    def test_population_formatted(self):
        """Populations must be comma-formatted in the HTML output."""
        self.assertIn("1,400,000,000", self.html_content)
        self.assertIn("500,000,000", self.html_content)

    def test_flag_img_tags_present(self):
        """Each country row must contain an <img> tag for the flag."""
        imgs = self.soup.find_all("img")
        # One <img> per country
        self.assertEqual(len(imgs), len(self.countries))

    def test_flag_img_src_references_local_path(self):
        """Flag <img> src attributes must point to the local flag paths."""
        imgs = self.soup.find_all("img")
        src_values = [img["src"] for img in imgs]
        self.assertTrue(
            any("/fake/flags/alpha.png" in src for src in src_values)
        )
        self.assertTrue(
            any("/fake/flags/beta.png" in src for src in src_values)
        )

    def test_date_of_data_present(self):
        """Date strings from the fixture must appear in the HTML."""
        self.assertIn("2023", self.html_content)
        self.assertIn("2022", self.html_content)

    def test_output_file_written(self):
        """The output file must exist and be non-empty."""
        self.assertTrue(Path(self.output_path).exists())
        self.assertGreater(Path(self.output_path).stat().st_size, 0)
