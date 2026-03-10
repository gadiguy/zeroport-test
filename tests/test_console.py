"""Unit test: console output format and correctness."""

import sys
import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Minimal wikitable fixture matching actual Wikipedia column layout:
# 0=Location(flag+name)  1=Population  2=%world  3=Date  4=Source  5=Notes
# 3 data rows: 2 countries, Beta appearing twice
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


class TestConsoleOutput(unittest.TestCase):
    """Verify that the console renderer produces correct tabular output."""

    def _run_main_with_mock(self, extra_args: list[str] = None) -> str:
        """Run main() with a mocked HTTP response and captured stdout.

        Returns the captured stdout string.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = FIXTURE_HTML

        # Mock flag download so no real network calls are made
        def fake_download_all_flags(countries, flag_images_dir):
            for c in countries:
                c["flag_path"] = f"/fake/flags/{c['country_name']}.png"

        argv = ["main.py"] + (extra_args or [])

        with (
            patch("scraper.requests.get", return_value=mock_response),
            patch("main.download_all_flags", side_effect=fake_download_all_flags),
            patch("sys.argv", argv),
            patch.dict(
                "os.environ",
                {
                    "TARGET_URL": "http://fake.url",
                    "FLAG_IMAGES_DIR": "/tmp/flags",
                },
            ),
        ):
            captured = io.StringIO()
            sys.stdout = captured
            try:
                import main  # noqa: PLC0415
                # Re-run main() since module was already imported
                main.main()
            finally:
                sys.stdout = sys.__stdout__

        return captured.getvalue()

    def test_header_present(self):
        """Console output must contain column headers."""
        output = self._run_main_with_mock()
        self.assertIn("Country", output)
        self.assertIn("Population", output)
        self.assertIn("Date of Data", output)
        self.assertIn("Flag Path", output)

    def test_country_names_present(self):
        """Both country names from the fixture must appear in output."""
        output = self._run_main_with_mock()
        self.assertIn("Alpha", output)
        self.assertIn("Beta", output)

    def test_populations_formatted(self):
        """Populations must appear comma-formatted in output."""
        output = self._run_main_with_mock()
        self.assertIn("1,400,000,000", output)
        self.assertIn("500,000,000", output)

    def test_date_of_data_present(self):
        """Date strings from the fixture must appear in output."""
        output = self._run_main_with_mock()
        self.assertIn("2023", output)
        self.assertIn("2022", output)

    def test_flag_paths_present(self):
        """Mocked flag paths must appear in the console output."""
        output = self._run_main_with_mock()
        self.assertIn("/fake/flags/Alpha.png", output)
        self.assertIn("/fake/flags/Beta.png", output)

    def test_duplicate_country_listed_twice(self):
        """Beta appears twice in the fixture; two data rows must start with Beta."""
        output = self._run_main_with_mock()
        # Country name is the first column, so Beta rows start with "Beta"
        beta_rows = [line for line in output.splitlines() if line.startswith("Beta")]
        self.assertEqual(len(beta_rows), 2)

    def test_sorted_descending(self):
        """Alpha (1.4 B) must appear before Beta (500 M) in the output."""
        output = self._run_main_with_mock()
        alpha_pos = output.index("Alpha")
        beta_pos = output.index("Beta")
        self.assertLess(alpha_pos, beta_pos)

    def test_min_population_filter(self):
        """With --min_population 1000000000 only Alpha should appear."""
        output = self._run_main_with_mock(["--min_population", "1000000000"])
        self.assertIn("Alpha", output)
        self.assertNotIn("Beta", output)
