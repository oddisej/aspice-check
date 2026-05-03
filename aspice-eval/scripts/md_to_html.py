"""Convert a Markdown report file to HTML using the ReportGenerator converter."""
from __future__ import annotations

import sys
import pathlib

# Add src to path so we can import aspice_eval
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from aspice_eval.report_generator import ReportGenerator

if len(sys.argv) < 2:
    print("Usage: python md_to_html.py <input.md> [output.html]")
    sys.exit(1)

input_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")

md_content = input_path.read_text(encoding="utf-8")
html_content = ReportGenerator._markdown_to_html(md_content)
output_path.write_text(html_content, encoding="utf-8")

print(f"Converted {input_path} -> {output_path}")
