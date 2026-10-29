"""Explicit small syntax control, clarification outside its declared language."""
import re
from . import parser

ATOM=r'(?:by\s+"[^"\n]+"|titled\s+"[^"\n]+"|rated\s+(?:at\s+least|at\s+most|above|below)\s+\d(?:\.\d+)?|(?:include|exclude)\s+subject\s+"[^"\n]+"|exclude\s+whole\s+word\s+"[^"\n]+"|sort\s+by\s+(?:title|rating|newest|relevance)|online\s+only|physical\s+only|topic:\s*[^;]+)'


def parse(query,facets=(),mode='SMART',capabilities=None):
    if mode=='EXACT':return parser.validate(parser.parse_query(query,facets,mode),capabilities)
    if len(query)>500:raise ValueError('Query exceeds500 characters')
    if not re.fullmatch(r'\s*'+ATOM+r'(?:\s*;\s*'+ATOM+r')*\s*',query,re.I):
        p=parser.QueryPlan(query,'SMART');p.parser_version=parser.PARSER_VERSION
        return parser.decide(p,'AMBIGUOUS','RESTRICTED_LANGUAGE_CLARIFICATION',fields=['query'])
    return parser.validate(parser.parse_query(query,facets),capabilities)
