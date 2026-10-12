# Private document OCR

Uploaded PDFs first use native page text. Pages with insufficient letters or words,
a low alphabetic/printable ratio, or replacement/control characters use local OCR.
Healthy native pages are retained exactly. Blank pages skip OCR. A failed scanned
page keeps its page number; the other pages remain usable and the UI reports
“Some scanned pages could not be read.”

The configured defaults are in `rag/services/private_document_ocr.py`: 220 DPI,
12 million pixels per raster, one OCR page at a time, a 20-second page timeout,
80 OCR attempts per preparation, and at most two document preparation jobs.
The RGB raster lives only in memory and subprocess pipes. Extraction/OCR runs
outside the interactive GPU lock; only the existing document embedding phase
acquires that lock. OCR does not use the GPU or any external service.

## Local setup

PyMuPDF includes a Tesseract OCR engine and requires language data. See the
[PyMuPDF OCR documentation](https://pymupdf.readthedocs.io/en/latest/faq/index.html#OCR).
Place the small English `eng.traineddata` file from the official
[Tesseract fast language data repository](https://github.com/tesseract-ocr/tessdata_fast)
in `~/.cache/luminar/tessdata`, or set `TESSDATA_PREFIX` to its directory.
This environment already has that language pack; its pinned revision and SHA-256
are recorded in `reports/knowledge_tools_v2_1_ocr_preflight.json`.

An installed Tesseract CLI is also supported. It is discovered on PATH and at the
usual Windows installation paths, or can be selected with `LUMINAR_TESSERACT`.
No `pytesseract` package is needed. The application never downloads dependencies
at runtime. If local OCR is unavailable, native pages still work; an entirely
unreadable document returns a setup message.

## Lifecycle and evidence

OCR runs once during upload preparation. Chunks retain `NATIVE` or `OCR` and the
original page numbers. Ask Document and the shared knowledge model consume those
same chunks. Source links use the authenticated document source endpoint.
Prepared encrypted device copies preserve OCR markers and vectors, so restoring
them requires neither OCR nor the original PDF. Existing copies without OCR
markers remain compatible. Artifacts and knowledge models stay session-owned.
Logout, deletion, revocation and TTL cleanup remove server copies and derived
knowledge state through the existing private-document lifecycle.

Upload status is authenticated and scoped to the account, session and preparation
UUID. It exposes only `PREPARING_DOCUMENT` or `READING_SCANNED_PAGES`, with no
filename, source text or simulated percentage. Status disappears after completion
or failure. Reports contain timing/count/ID evidence rather than private text.

The lightweight English engine is suitable for clear printed notes. Handwriting,
complex formulas, poor scans and other languages can remain unreadable; question
generation continues to reject incomplete or ambiguous evidence.
