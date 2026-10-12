"""Disposable OCR process: only in-memory PNG input and UTF-8 text output."""
import sys
import pymupdf

if __name__=='__main__':
    try:
        blob=sys.stdin.buffer.read(20_000_001)
        if len(blob)>20_000_000:
            raise ValueError('Raster too large')
        pix=pymupdf.Pixmap(blob)
        pdf=pymupdf.open('pdf',pix.pdfocr_tobytes(language='eng',tessdata=sys.argv[1]))
        text=pdf[0].get_text()
        pdf.close()
        sys.stdout.buffer.write(text.encode('utf8'))
    except Exception:
        # Do not echo engine errors or OCR text into application logs.
        sys.exit(1)
