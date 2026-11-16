from __future__ import annotations

import argparse
from pathlib import Path

import markdown


CSS = r"""
@page {
  size: Letter;
  margin: 0.72in 0.78in 0.72in;
  @bottom-center {
    content: counter(page);
    color: #50605d;
    font: 9pt "Inter", "Arial", sans-serif;
  }
}

:root {
  --ink: #15211f;
  --muted: #4e5f5b;
  --line: #bfd3cd;
  --accent: #087f72;
  --wash: #eff7f4;
}

* { box-sizing: border-box; }

html { background: #ffffff; }

body {
  color: var(--ink);
  font-family: "Source Serif 4", "Georgia", serif;
  font-size: 10.4pt;
  line-height: 1.46;
  margin: 0;
  hyphens: auto;
}

h1, h2, h3 {
  break-after: avoid;
  color: #0d2b27;
  font-family: "Inter", "Arial", sans-serif;
  line-height: 1.12;
}

h1 {
  border-top: 8px solid var(--accent);
  font-size: 30pt;
  letter-spacing: -0.035em;
  margin: 0 0 0.12in;
  padding-top: 0.22in;
}

h1 + h2 {
  border: 0;
  color: var(--muted);
  font-family: "Source Serif 4", "Georgia", serif;
  font-size: 16pt;
  font-style: italic;
  font-weight: normal;
  margin: 0 0 0.22in;
  padding: 0;
}

h2 {
  border-top: 1px solid var(--line);
  font-size: 16pt;
  margin: 0.28in 0 0.12in;
  padding-top: 0.12in;
}

h3 {
  color: var(--accent);
  font-size: 11.5pt;
  margin: 0.2in 0 0.07in;
  text-transform: none;
}

p { margin: 0 0 0.1in; orphans: 3; widows: 3; }

strong { color: #0d5149; }

ul, ol {
  margin: 0.05in 0 0.13in 0.22in;
  padding-left: 0.18in;
}

li { margin-bottom: 0.04in; }

table {
  border-collapse: collapse;
  break-inside: avoid;
  font-family: "Inter", "Arial", sans-serif;
  font-size: 8.6pt;
  line-height: 1.3;
  margin: 0.13in 0 0.19in;
  width: 100%;
}

th {
  background: #dff0eb;
  color: #0d5149;
  font-weight: 700;
  text-align: left;
}

th, td {
  border: 1px solid var(--line);
  padding: 0.08in;
  vertical-align: top;
}

tr:nth-child(even) td { background: #f8fbfa; }

a { color: #06695f; overflow-wrap: anywhere; text-decoration: none; }

code {
  background: var(--wash);
  border-radius: 3px;
  font-size: 0.9em;
  padding: 0.01in 0.03in;
}

blockquote {
  border-left: 3px solid var(--accent);
  color: var(--muted);
  margin: 0.12in 0;
  padding-left: 0.13in;
}

body > p:nth-of-type(1) {
  color: var(--muted);
  font-family: "Inter", "Arial", sans-serif;
  font-size: 9.5pt;
  margin-bottom: 0.3in;
}

body > h2:nth-of-type(2) + p {
  background: var(--wash);
  border-left: 4px solid var(--accent);
  font-size: 10pt;
  padding: 0.14in 0.16in;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    body = markdown.markdown(
        args.source.read_text(encoding="utf-8"),
        extensions=["tables", "sane_lists"],
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Observer Is Inside the Machine</title>
  <style>{CSS}</style>
</head>
<body>{body}</body>
</html>
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
