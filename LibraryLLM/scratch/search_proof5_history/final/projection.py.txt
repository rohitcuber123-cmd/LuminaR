"""Pure native-field projection, no parser fallback."""
import re
from .proposals import FAMILIES
def _apply(plan,items,changed):
    for family in changed:
        for name in FAMILIES.get(family,[]):
            setattr(plan,name,[] if isinstance(getattr(plan,name),list) else False if isinstance(getattr(plan,name),bool) else 'RELEVANCE' if name=='sort' else None)
    for c in items:
        f,op,v=c.field,c.operator,c.normalized_value
        if f not in changed or c.support_status!='SUPPORTED':continue
        if f in ['rating','year']:
            bounds=[('min',v[0],False),('max',v[1],False)] if op=='RANGE' else [('min',v,False),('max',v,False)] if op=='=' else [('min' if op in ['>','>='] else 'max',v,op in ['>','<'])]
            for side,value,exclusive in bounds:
                key=f+'_'+side;old=getattr(plan,key)
                if old is None or (value>old if side=='min' else value<old):setattr(plan,key,value);setattr(plan,key+'_exclusive',exclusive)
                elif value==old:setattr(plan,key+'_exclusive',getattr(plan,key+'_exclusive') or exclusive)
        elif f=='subject':plan.subjects.append(v);plan.include_terms.append(v)
        elif f=='excluded_subject':plan.exclude_subjects.append(v)
        elif f=='exclude':
            if op=='TEXT_NOT':plan.exclude_terms.append(v)
            else:
                for term in re.split(r'\s*(?:,|\band\b|\bor\b)\s*',str(v)):
                    if term.strip():plan.exclude_terms.append(term.strip())
        elif f=='format':
            plan.formats.append(v)
            if op=='ONLY':plan.exclusive_formats.append(v)
        elif f=='excluded_format':plan.excluded_formats.append(v)
        elif f=='author':plan.author_text=v
        elif f=='title':plan.title_text=v
        elif f=='sort':plan.sort=v
        elif f=='availability':
            plan.availability='AVAILABLE_NOW' if v=='PHYSICAL_NOW' else 'REQUESTABLE' if v=='PHYSICAL_REQUESTABLE' else v
            if v in ['PHYSICAL_NOW','PHYSICAL_REQUESTABLE']:plan.physical_available_only=True
        elif f=='language':plan.language=v
    for key in ['subjects','include_terms','exclude_terms','exclude_subjects','formats','exclusive_formats','excluded_formats']:
        setattr(plan,key,list(dict.fromkeys(getattr(plan,key))))
