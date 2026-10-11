"""Extract text from snapshotted PDFs to sibling .txt files (for quote verification).

Usage: .venv\\Scripts\\python.exe scripts/extract_pdf_text.py
"""
from pathlib import Path

from pypdf import PdfReader

SRC = Path(__file__).resolve().parents[1] / "data" / "sources"

for pdf in sorted(SRC.glob("*.pdf")):
    out = pdf.with_suffix(".txt")
    try:
        reader = PdfReader(str(pdf))
        text = "\n\n".join(f"--- page {i + 1} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages))
        out.write_text(text, encoding="utf-8")
        print(f"ok  {pdf.name}: {len(reader.pages)} pages, {len(text)} chars")
    except Exception as exc:
        print(f"ERR {pdf.name}: {exc}")
