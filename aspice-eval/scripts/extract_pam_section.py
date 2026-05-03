"""Extract specific sections from the ASPICE PAM v4.0 PDF."""
import fitz
import sys
import re

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "files/Automotive-SPICE-PAM-v40.pdf"
search_term = sys.argv[2] if len(sys.argv) > 2 else "SWE.1"
page_range = sys.argv[3] if len(sys.argv) > 3 else None  # e.g., "50-70"

doc = fitz.open(pdf_path)

if page_range:
    start, end = map(int, page_range.split("-"))
    pages = range(start - 1, min(end, doc.page_count))
else:
    # Find pages containing the search term
    pages = []
    for i in range(doc.page_count):
        text = doc[i].get_text()
        if search_term in text:
            pages.append(i)

print(f"Found '{search_term}' on {len(pages)} pages: {[p+1 for p in pages]}")
print("=" * 80)

for p in pages:
    text = doc[p].get_text()
    print(f"\n--- PAGE {p + 1} ---")
    print(text)

doc.close()
