"""Selective, local, bounded OCR. Page rasters exist only in memory/pipes."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from threading import Semaphore
import time

import pymupdf

_pages = Semaphore(1)


@dataclass(frozen=True)
class OCRConfig:
    dpi: int = 220
    min_letters: int = 30
    min_words: int = 6
    min_alpha_ratio: float = .40
    min_printable_ratio: float = .97
    max_bad_ratio: float = .02
    max_pixels: int = 12_000_000
    page_timeout: int = 20
    page_limit: int = 80


CONFIG = OCRConfig()


def usable(text, config=CONFIG):
    chars=[c for c in text if not c.isspace()]
    if not chars:
        return False
    alpha=sum(c.isalpha() for c in chars)
    bad=sum(c=='\ufffd' or not c.isprintable() for c in chars)
    words=re.findall(r'[^\W\d_]{2,}',text,flags=re.UNICODE)
    return (alpha>=config.min_letters and len(words)>=config.min_words
            and alpha/len(chars)>=config.min_alpha_ratio
            and sum(c.isprintable() for c in chars)/len(chars)>=config.min_printable_ratio
            and bad/len(chars)<=config.max_bad_ratio)


def capability():
    executable=os.environ.get('LUMINAR_TESSERACT') or shutil.which('tesseract')
    for path in [Path('C:/Program Files/Tesseract-OCR/tesseract.exe'),Path('C:/Program Files (x86)/Tesseract-OCR/tesseract.exe')]:
        if not executable and path.is_file():
            executable=str(path)
    locations=[os.environ.get('TESSDATA_PREFIX'),str(Path.home()/'.cache/luminar/tessdata')]
    if executable:
        locations.insert(0,str(Path(executable).parent/'tessdata'))
    tessdata=next((str(Path(p)) for p in locations if p and (Path(p)/'eng.traineddata').is_file()),None)
    return {'available':bool(executable or tessdata),'engine':'tesseract-cli' if executable else 'pymupdf-tesseract',
            'executable':executable,'tessdata':tessdata}


def read_page(page, config=CONFIG):
    cap=capability()
    if not cap['available']:
        raise RuntimeError('OCR_NOT_CONFIGURED')
    if not _pages.acquire(timeout=config.page_timeout):
        raise RuntimeError('OCR_BUSY')
    try:
        area=page.rect.width*page.rect.height
        if not math.isfinite(area) or area<=0:
            raise RuntimeError('OCR_INVALID_PAGE_SIZE')
        dpi=min(config.dpi,int(72*math.sqrt(config.max_pixels/area)))
        if dpi<72:
            raise RuntimeError('OCR_PAGE_TOO_LARGE')
        pixels=(math.ceil(page.rect.width*dpi/72)+2)*(math.ceil(page.rect.height*dpi/72)+2)
        if pixels>config.max_pixels:
            dpi-=1
        if dpi<72 or (math.ceil(page.rect.width*dpi/72)+2)*(math.ceil(page.rect.height*dpi/72)+2)>config.max_pixels:
            raise RuntimeError('OCR_PAGE_TOO_LARGE')
        # Embedded Tesseract requires RGB; grayscale yielded empty OCR on 1.28.
        pix=page.get_pixmap(dpi=dpi,colorspace=pymupdf.csRGB,alpha=False)
        raster_bytes=pix.width*pix.height*3
        png=pix.tobytes('png')
        del pix
        env={**os.environ,'OMP_THREAD_LIMIT':'1'}
        if cap['executable']:
            command=[cap['executable'],'stdin','stdout','-l','eng','--dpi',str(dpi)]
            if cap['tessdata']:
                command+=['--tessdata-dir',cap['tessdata']]
        else:
            command=[sys.executable,'-m','rag.services.private_ocr_worker',cap['tessdata']]
        result=subprocess.run(command,input=png,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=config.page_timeout,env=env,cwd=Path(__file__).resolve().parents[2],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode or len(result.stdout)>1_000_000:
            raise RuntimeError('OCR_FAILED')
        # stderr may contain text from a damaged document; never expose or log it.
        return result.stdout.decode('utf8',errors='replace').strip(),raster_bytes
    finally:
        _pages.release()


def prepare(path, native_pages, reader=read_page, config=CONFIG, progress=None):
    started=time.perf_counter()
    stats={'native_pages':0,'ocr_pages':0,'ocr_attempts':0,'failed_pages':0,'blank_pages':0,
           'peak_raster_bytes':0,'page_limit':config.page_limit,'dpi':config.dpi,'concurrent_pages':1}
    pages=[]
    with pymupdf.open(path) as pdf:
        if len(pdf)!=len(native_pages):
            raise ValueError('Page identity mismatch')
        for index,record in enumerate(native_pages):
            row=dict(record,extraction_method='NATIVE')
            if usable(row['text'],config):
                stats['native_pages']+=1
            else:
                page=pdf[index]
                blank=not row['text'].strip() and not page.get_images() and not page.get_drawings()
                if blank:
                    row['text']='';stats['blank_pages']+=1
                elif stats['ocr_attempts']>=config.page_limit:
                    row['text']='';stats['failed_pages']+=1
                else:
                    stats['ocr_attempts']+=1
                    if progress:
                        progress('READING_SCANNED_PAGES')
                    try:
                        text,memory=reader(page,config)
                        stats['peak_raster_bytes']=max(stats['peak_raster_bytes'],memory)
                        if not usable(text,config):
                            raise ValueError('Unusable OCR text')
                        row['text']=text;row['extraction_method']='OCR';stats['ocr_pages']+=1
                    except (RuntimeError,ValueError,OSError,subprocess.SubprocessError):
                        # Keep the rest of the document usable, preserving this page number.
                        row['text']='';stats['failed_pages']+=1
            pages.append(row)
    stats['preparation_ms']=round((time.perf_counter()-started)*1000,2)
    return pages,stats
