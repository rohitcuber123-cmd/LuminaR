"""Source-preserving soft projection and the existing product preference vocabulary.

No hard filter is authorized here. Quoted operands are opaque while grammatical
request framing is removed; punctuation inside technical terms is retained.
"""
import re,unicodedata
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import outside

GENERIC=r'(?:stories|novels|biographies|works|writings)'
CONSERVATIVE={'women','men','general','science','education','research','law','computers','networks','war','love'}
PREFERENCES=[
 (r'\b(?:short|shorter)\b','Prefer shorter books','DISCOVER_TOPIC'),
 (r'\b(?:introductory|beginner(?:s)?|first[ -]year)\b','Introductory / beginner (preference)','LEARN'),
 (r'\b(?:advanced|research[ -]level)\b','Advanced (preference)','RESEARCH')]
FRAME=re.compile(r'\b(?:books?|novels?|copies|materials?|please|find|show|me|about|on|with|and|but|then|ratings?|rated|stars?)\b',re.I)

def generic_topic(text):return bool(re.search(r'\b'+GENERIC+r'\s+(?:about|on)\s+',outside(text),re.I))

def claim_preferences(s):
    for pattern,value,intent in PREFERENCES:
        for m in re.finditer(pattern,s.remaining(protect=True)):
            a,b=m.span()
            # A suffix audience complement owns its preposition as well.
            prefix=s.text[:a]
            prep=re.search(r'\bfor\s+$',prefix)
            if prep:a=prep.start()
            if not s.free(a,b):continue
            # An explicitly mandatory measurable descriptor cannot be softened.
            clause=re.split(r'[;.!?]',s.text[:a])[-1]
            if re.search(r'\b(?:must|required?|mandatory|strict)\b',outside(clause)):continue
            from scratch.search_v2c_c5er.candidate_search_v4.query_constraints import Candidate
            x,y=s.span(a,b)
            s.items.append(Candidate('preference','SOFT',value,x,y,s.raw[x:y],'surface.descriptive_preference',ownership='ADVISORY',representation='ADVISORY'))

def claim_frames(s):
    from scratch.search_v2c_c5er.candidate_search_v4.query_constraints import Candidate
    for c in list(s.items):
        if c.field not in ['format','rating','year']:continue
        pattern=r'\b(?:available|i\s+can\s+read)\s+$' if c.field=='format' else r'\b(?:and|but)\s+(?:stay|remain|be)\s+$'
        m=re.search(pattern,s.raw[:c.source_span_start],re.I)
        if m and not any(m.start()<x.source_span_end and m.end()>x.source_span_start for x in s.items):
            s.items.append(Candidate('connector','GRAMMAR',None,*m.span(),s.raw[m.start():m.end()],'surface.format_frame',representation='GRAMMAR'))

def render(values,*,generic=False):
    text=' '.join(v for v in values if v)
    text=unicodedata.normalize('NFKC',text).casefold()
    if generic:return ' '.join(text.strip().split()) or None
    # Protect literal bodies while stripping request framing outside them.
    protected=[]
    def save(m):protected.append(m[1] if m[1] is not None else m[2]);return f' zzliteral{len(protected)-1}zz '
    text=re.sub(r'"([^"\n]*)"|“([^”\n]*)”',save,text)
    text=FRAME.sub(' ',text)
    text=re.sub(r'^\s*of\s+','',text)
    text=re.sub(r'^[ ,;:!?]+(?!\.[a-zA-Z])|[ ,;!?]+$','',text.strip())
    text=' '.join(text.split())
    # A terminal sentence period is framing; a leading .NET or interior C++
    # punctuation remains part of the actual semantic operand.
    text=re.sub(r'(?<=\w)\.$','',text)
    for i,value in enumerate(protected):text=text.replace(f'zzliteral{i}zz',value)
    return ' '.join(text.split()) or None

def semantic_projection(ir):
    ambiguous=[r for r in ir.requirements if r.field=='ambiguous_number']
    parts=[(r.source_span[0],r.value) for r in ir.requirements if r.field in ['semantic_residue','semantic']]
    if ambiguous:
        seen_spans=set()
        for r in ambiguous:
            if r.source_span not in seen_spans:
                seen_spans.add(r.source_span);parts.append((r.source_span[0],r.source_text))
        for r in ir.requirements:
            if r.field=='subject' and r.source_span not in seen_spans:
                seen_spans.add(r.source_span);parts.append((r.source_span[0],r.source_text))
    result=render([v for _,v in sorted(parts)],generic=generic_topic(ir.raw_query))
    if 'topic' in ir.trusted_controls.get('omit',()):result=None
    return result

def residual_segments(source,a,b):
    """Subtract exact raw source ownership; do not infer boundaries from spaces."""
    ranges=sorted((max(a,c.source_span_start),min(b,c.source_span_end)) for c in source.items if c.source_span_start<b and c.source_span_end>a)
    cursor=a
    for x,y in ranges:
        if x>cursor:yield cursor,x,source.raw[cursor:x]
        cursor=max(cursor,y)
    if cursor<b:yield cursor,b,source.raw[cursor:b]
