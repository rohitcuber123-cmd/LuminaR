"""Contain unsupported numeric page citations at the HTTP integration boundary.

Evidence-stage verdicts are not final-answer validators. This check only
downgrades a generated page attribution unsupported by returned page metadata;
it does not reinterpret an ordinary abstention or validate the answer's facts.
"""
import re

PAGE_REFERENCE=re.compile(
    r'\b(?:pages?|pp?\.|pgs?\.)\s*(?:(?:number|no\.)\s*)?[:#]?\s*'
    r'(?P<locations>-?\d{1,9}(?:(?:\s*[-–—,]\s*|\s+and\s+)-?\d{1,9})*)\b',re.I)

def _supported_locations(locations,pages):
    for part in re.split(r'\s*(?:,|\band\b)\s*',locations,flags=re.I):
        span=re.fullmatch(r'(-?\d+)\s*[-–—]\s*(-?\d+)',part)
        if span:
            first,last=map(int,span.groups())
            if first<1 or last<first or last-first>1000:return False
            if any(page not in pages for page in range(first,last+1)):return False
        elif int(part) not in pages:return False
    return True

def validate_page_claims(result):
    """Keep valid responses byte-for-field equivalent; never mutate inputs."""
    answer=result.get('answer')
    if not isinstance(answer,str):return result
    pages=set()
    for source in result.get('sources') or []:
        if not isinstance(source,dict):continue
        page=source.get('page')
        if type(page) is int and page>0:pages.add(page)
        elif isinstance(page,str) and re.fullmatch(r'[1-9]\d*',page.strip()):pages.add(int(page))
    claims=[match['locations'] for match in PAGE_REFERENCE.finditer(answer)]
    # A bare number is a page attribution only for a page-location question,
    # not a page-count, stock-count, date or other numeric answer.
    question=str(result.get('question') or '')
    location_question=bool(re.search(
        r'\b(?:which|what)\s+page\b|\b(?:exact\s+page|page\s+(?:number|location))\b',question,re.I)) and not bool(re.search(
        r'\bpage\s*count\b|\bnumber of pages\b|\bhow many pages\b',question,re.I))
    if location_question and not pages:
        return {**result,'answer':'An exact source page for this answer is not established by the supplied source metadata.',
                'verdict':'NOT_SUPPORTED'}
    if (not claims and re.fullmatch(r'\s*\d{1,9}[.!]?\s*',answer)
            and re.search(r'\bpage\b',question,re.I)
            and not re.search(r'page\s*count|number of pages|how many pages',question,re.I)):
        claims=[re.search(r'\d+',answer).group()]
    if not claims or all(_supported_locations(claim,pages) for claim in claims):return result
    return {**result,'answer':'An exact source page for this answer is not established by the supplied source metadata.',
            'verdict':'NOT_SUPPORTED'}
