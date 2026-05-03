"""Convert a Markdown report file to Confluence wiki markup.

Confluence wiki markup reference:
  https://confluence.atlassian.com/doc/confluence-wiki-markup-251003035.html

Usage:
    python md_to_confluence.py <input.md> [output.wiki]
"""
from __future__ import annotations

import re
import sys
import pathlib


def md_to_confluence(md: str) -> str:
    """Convert Markdown to Confluence wiki markup.

    Handles: headings, tables, unordered/ordered lists (with nesting),
    bold, italic, code, links, horizontal rules, and paragraphs.
    """
    lines = md.split("\n")
    out: list[str] = []
    i = 0

    # Track list state for blank-line handling
    in_list = False

    while i < len(lines):
        line = lines[i]

        # --- YAML front-matter: skip ---
        if line.strip() == "---" and i == 0:
            i += 1
            while i < len(lines) and lines[i].strip() != "---":
                i += 1
            i += 1  # skip closing ---
            continue

        # --- Headings: # → h1., ## → h2., etc. ---
        hm = re.match(r"^(#{1,6})\s+(.+)$", line)
        if hm:
            in_list = False
            level = len(hm.group(1))
            text = _inline(hm.group(2))
            out.append(f"h{level}. {text}")
            out.append("")
            i += 1
            continue

        # --- Horizontal rule ---
        if line.strip() == "---":
            in_list = False
            out.append("----")
            out.append("")
            i += 1
            continue

        # --- Table rows ---
        if line.startswith("|"):
            in_list = False
            # Skip separator rows
            if re.match(r"^\|[-|:\s]+\|$", line):
                i += 1
                continue

            cells = [c.strip() for c in line.split("|")[1:-1]]

            # Detect header row: check if next line is a separator
            is_header = (
                i + 1 < len(lines)
                and re.match(r"^\|[-|:\s]+\|$", lines[i + 1])
            )

            if is_header:
                row = "||" + "||".join(_inline(c) for c in cells) + "||"
            else:
                row = "|" + "|".join(_inline(c) for c in cells) + "|"

            out.append(row)
            i += 1
            continue

        # --- Unordered list items ---
        ul_match = re.match(r"^(\s*)- (.+)$", line)
        if ul_match:
            indent = len(ul_match.group(1))
            depth = (indent // 2) + 1  # 0 spaces = *, 2 spaces = **, etc.
            text = _inline(ul_match.group(2))
            out.append(f"{'*' * depth} {text}")
            in_list = True
            i += 1
            continue

        # --- Ordered list items ---
        ol_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
        if ol_match:
            indent = len(ol_match.group(1))
            depth = (indent // 2) + 1
            text = _inline(ol_match.group(3))
            out.append(f"{'#' * depth} {text}")
            in_list = True
            i += 1
            continue

        # --- Empty lines ---
        if not line.strip():
            if in_list:
                in_list = False
            i += 1
            continue

        # --- Paragraph text ---
        in_list = False
        out.append(_inline(line))
        out.append("")
        i += 1

    return "\n".join(out) + "\n"


def _inline(text: str) -> str:
    """Convert inline Markdown formatting to Confluence wiki markup."""
    # Bold + italic: ***text*** → *_text_*
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"*_\1_*", text)
    # Bold: **text** → *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Italic: *text* → _text_ (but not inside bold markers)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"_\1_", text)
    # Inline code: `text` → {{text}}
    text = re.sub(r"`([^`]+?)`", r"{{\1}}", text)
    # Links: [text](url) → [text|url]
    text = re.sub(r"\[([^\]]+?)\]\(([^)]+?)\)", r"[\1|\2]", text)
    # Images: ![alt](path) → !path|alt=alt!
    text = re.sub(r"!\[([^\]]*?)\]\(([^)]+?)\)", r"!\2|alt=\1!", text)
    # Strikethrough: ~~text~~ → -text-
    text = re.sub(r"~~(.+?)~~", r"-\1-", text)
    return text


# --- CLI entry point ---

if len(sys.argv) < 2:
    print("Usage: python md_to_confluence.py <input.md> [output.wiki]")
    sys.exit(1)

input_path = pathlib.Path(sys.argv[1])
output_path = (
    pathlib.Path(sys.argv[2])
    if len(sys.argv) > 2
    else input_path.with_suffix(".wiki")
)

md_content = input_path.read_text(encoding="utf-8")
wiki_content = md_to_confluence(md_content)
output_path.write_text(wiki_content, encoding="utf-8")

print(f"Converted {input_path} -> {output_path}")
