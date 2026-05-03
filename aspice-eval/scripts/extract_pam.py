"""Extract text from the ASPICE PAM v4.0 PDF."""
import fitz  # pymupdf
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "files/Automotive-SPICE-PAM-v40.pdf"

doc = fitz.open(pdf_path)
print(f"Total pages: {doc.page_count}")
print("=" * 80)

# Extract all text
for page_num in range(doc.page_count):
    page = doc[page_num]
    text = page.get_text()
    if text.strip():
        print(f"\n--- PAGE {page_num + 1} ---")
        print(text)

doc.close()
