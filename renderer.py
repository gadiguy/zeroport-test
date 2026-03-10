"""Format country data for console (stdout) and HTML file output."""

import html as html_lib
from pathlib import Path


# Column widths for the fixed-width console table
_COL_WIDTHS = {
    "country_name": 40,
    "population": 15,
    "date_of_data": 20,
    "flag_path": 60,
}


def render_console(countries: list[dict]) -> str:
    """Format the country list as a fixed-width text table string.

    Columns: Country | Population | Date of Data | Flag Path
    """
    # Build the header row using the same widths as the data rows
    header = (
        "Country".ljust(_COL_WIDTHS["country_name"])
        + "  "
        + "Population".ljust(_COL_WIDTHS["population"])
        + "  "
        + "Date of Data".ljust(_COL_WIDTHS["date_of_data"])
        + "  "
        + "Flag Path"
    )

    # Separator line matching the total header width
    separator = "-" * len(header)

    lines = [header, separator]

    for c in countries:
        # Show the local path on success, or a short error reason on failure
        if c["flag_path"]:
            flag_path = c["flag_path"]
        else:
            flag_path = f"(error: {c.get('flag_error', 'unknown')})"
        line = (
            c["country_name"].ljust(_COL_WIDTHS["country_name"])
            + "  "
            + f"{c['population']:,}".ljust(_COL_WIDTHS["population"])
            + "  "
            + c["date_of_data"].ljust(_COL_WIDTHS["date_of_data"])
            + "  "
            + flag_path
        )
        lines.append(line)

    return "\n".join(lines)


def render_html(countries: list[dict], output_path: str) -> None:
    """Write the country list as a styled HTML table to output_path.

    Each row includes an inline <img> referencing the local flag file.
    """
    # Build the table rows, HTML-escaping all text content
    rows: list[str] = []
    for c in countries:
        flag_path = c.get("flag_path") or ""

        # Render flag as an <img> on success, or a short error note on failure
        if flag_path:
            flag_cell = (
                f'<img src="{html_lib.escape(flag_path)}" '
                f'alt="{html_lib.escape(c["country_name"])} flag" '
                f'height="20">'
            )
        else:
            error_reason = html_lib.escape(c.get("flag_error", "unknown"))
            flag_cell = f'<em title="{error_reason}">error: {error_reason}</em>'

        # Pre-format population so it can be safely used inside html_lib.escape
        pop_str = f"{c['population']:,}"
        rows.append(
            "<tr>"
            f"<td>{html_lib.escape(c['country_name'])}</td>"
            f"<td>{html_lib.escape(pop_str)}</td>"
            f"<td>{html_lib.escape(c['date_of_data'])}</td>"
            f"<td>{flag_cell}</td>"
            "</tr>"
        )

    rows_html = "\n        ".join(rows)

    # Assemble a self-contained HTML document with embedded styles
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Countries by Population</title>
  <style>
    body {{ font-family: sans-serif; padding: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
    th {{ background: #f0f0f0; }}
    tr:nth-child(even) {{ background: #fafafa; }}
  </style>
</head>
<body>
  <h1>Countries and Dependencies by Population</h1>
  <table>
    <thead>
      <tr>
        <th>Country</th>
        <th>Population</th>
        <th>Date of Data</th>
        <th>Flag</th>
      </tr>
    </thead>
    <tbody>
        {rows_html}
    </tbody>
  </table>
</body>
</html>
"""

    # Write the HTML document to the specified output path
    Path(output_path).write_text(document, encoding="utf-8")
