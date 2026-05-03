"""Extract all process details from the ASPICE PAM v4.0 PDF and save to text files."""
import fitz
import sys
import os

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "files/Automotive-SPICE-PAM-v40.pdf"
output_dir = "aspice-eval/scripts/pam_extracts"
os.makedirs(output_dir, exist_ok=True)

doc = fitz.open(pdf_path)

# Page ranges for each section (from table of contents)
sections = {
    "swe": (45, 58),      # SWE.1-SWE.6
    "sys": (24, 44),      # SYS.1-SYS.5 (includes ACQ/SPL before)
    "sup": (79, 88),      # SUP.1, SUP.8, SUP.9, SUP.10
    "man": (89, 94),      # MAN.3, MAN.5, MAN.6
    "capability_levels": (99, 117),  # PA 1.1 through PA 5.2
    "info_items": (118, 153),  # Information items appendix
}

for name, (start, end) in sections.items():
    output_path = os.path.join(output_dir, f"{name}.txt")
    with open(output_path, "w") as f:
        for page_num in range(start - 1, min(end, doc.page_count)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                f.write(f"\n--- PAGE {page_num + 1} ---\n")
                f.write(text)
    print(f"Extracted {name}: pages {start}-{end} -> {output_path}")

doc.close()
print("Done!")
