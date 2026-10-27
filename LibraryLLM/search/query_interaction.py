"""Server-issued, single-use interactions over the accepted typed query plan.

This module does not recognize query syntax. Choices come from the parser's
decision/candidates and edit only the field named by that decision. The existing
parser parses every proposed operand; the existing validator guards the result.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from contextlib import contextmanager
import math

from fastapi import HTTPException
from search.query_plan import PARSER_VERSION, FacetVocabulary, normalize, parse_query
from search.query_confidence import decide, validate, executable
from search.session_store import collection, identity, token

LIFETIME_SECONDS=300
MAX_PENDING=16


def choices_for(plan, capabilities):
    decision=plan.decision; reason=decision.get('reason_code','')
    kind=decision.get('decision_type'); choices=[]; question=decision.get('safe_public_message','')
    def add(label, operation, **values):
        choices.append({'label':label,'operation':operation,**values})
    if kind=='AMBIGUOUS':
        fragments=decision.get('unresolved_fragments',[])
        # Read the parser's evidence, never guess that a digit is a rating.
        numeric=[c for c in plan.constraint_candidates if c['field']=='ambiguous_number']
        values=[c['normalized_value'] for c in numeric]
        if not values:
            for fragment in fragments:
                text=fragment.get('text','') if isinstance(fragment,dict) else str(fragment)
                try:values.append(float(text))
                except ValueError:pass
        if len(values)==1 and 0<=float(values[0])<=5:
            value=float(values[0]);question=f'What does {value:g} mean?'
            add(f'Rating of at least {value:g}','ambiguous_rating',value=value)
        add(f'Search “{plan.raw_query}” literally','literal')
    elif kind=='INCOMPLETE':
        fields=decision.get('affected_fields',[])
        candidates=[c for c in plan.constraint_candidates if c.get('support_status')=='INCOMPLETE']
        field=next((c['field'] for c in candidates if c['field'] in ('rating','year','author')),None)
        field=field or next((f for f in fields if f in ('rating','year','author')),None)
        if field=='rating':
            question='What rating should these books be above?' if any('above' in str(f) for f in decision.get('unresolved_fragments',[])) else 'What rating should these books use?'
            add('Apply rating','complete',field='rating',input_type='number',minimum=0,maximum=5)
        elif field=='year' and capabilities.get('year'):
            question='Which publication year should these books use?'
            add('Apply year','complete',field='year',input_type='number',minimum=1000,maximum=2100)
        elif field=='author':
            question='Which author do you mean?'
            add('Apply author','complete',field='author',input_type='text')
    elif reason in ('INCOMPATIBLE_RATING_BOUNDS','INCOMPATIBLE_YEAR_BOUNDS'):
        field='rating' if 'RATING' in reason else 'year'
        question=f'These {"publication-year" if field=="year" else field} filters conflict.'
        if capabilities.get(field,True):
            for side,symbol in [('min','>'),('max','<')]:
                value=getattr(plan,field+'_'+side)
                exclusive=getattr(plan,field+'_'+side+'_exclusive')
                op=symbol if exclusive else symbol+'='
                add(f'Keep {field} {op} {value:g}','bound',field=field,side=side,value=value,exclusive=exclusive)
        add(f'Remove {field} filter','remove',field=field)
    elif reason in ('EXCLUSIVE_FORMATS','FORMAT_INCLUDE_EXCLUDE'):
        question='These exclusive format requirements conflict.'
        for fmt,label in [('ONLINE','Online format'),('PHYSICAL','Physical format'),('BOTH','Both online and physical')]:
            if fmt in capabilities.get('formats',['ONLINE','PHYSICAL','BOTH']):add(label,'format',value=fmt)
    elif reason=='SUBJECT_INCLUDE_EXCLUDE':
        overlap=[s for s in plan.subjects if normalize(s) in set(map(normalize,plan.exclude_subjects))]
        if overlap:
            question=f'{", ".join(overlap)} {"is" if len(overlap)==1 else "are"} both included and excluded.'
            for action,label in [('include','Include'),('exclude','Exclude'),('neither','Remove both constraints for')]:
                add(label+' '+', '.join(overlap),'subject',action=action,subjects=overlap)
    elif kind=='UNSUPPORTED':
        fields=decision.get('affected_fields',[])
        if reason.startswith('SCOPE_'):
            field=reason.removeprefix('SCOPE_').removesuffix('_UNSUPPORTED').lower()
            add('Remove unsupported '+field+' filter','remove',field=field)
        elif any(c['field']=='page_count' or c['field']=='pages' for c in plan.constraint_candidates):
            question='An exact page-count filter is not available for this catalogue.'
            add('Remove the page-count requirement','unsupported_remove',fields=['pages','page_count'])
    if executable(plan) and plan.corrections:
        correction=next((c for c in plan.corrections if c.get('kind') in ('typo','alias')),None)
        if correction:
            question=f'Interpreted “{correction["from"]}” as “{correction["to"]}”.'
            add('Apply correction','correction_apply',correction=correction)
            add('Keep original wording','correction_keep',correction=correction)
    return question,choices


def offer(plan,session,actor,*,query,mode,filters,omit,session_id,capabilities,library_id=None,staff=False):
    # Legacy tokens without a login sid cannot own an interaction.
    if not actor.get('sid'):return None
    question,choices=choices_for(plan,capabilities)
    if not choices:return None
    now=datetime.now(timezone.utc);owner=identity(actor,library_id,staff)
    coll=collection(); cid=str(uuid4())
    rows=[dict(choice,choice_id=str(uuid4())) for choice in choices]
    row={'_id':'clarification:'+cid,'record_type':'CLARIFICATION',**owner,
         'query':query,'mode':mode,'filters':filters or {},'omit':list(omit),'search_session_id':session_id,
         'base_version':session['version'] if session else 0,'parser_version':PARSER_VERSION,
         'decision_type':plan.decision.get('decision_type'),'reason_code':plan.decision.get('reason_code'),
         'choices':rows,'created_at':now,'updated_at':now,'expires_at':now+timedelta(seconds=LIFETIME_SECONDS)}
    old=list(coll.find({**owner,'record_type':'CLARIFICATION'},{'_id':1}).sort('updated_at',-1).skip(MAX_PENDING-1))
    if old:coll.delete_many({'_id':{'$in':[r['_id'] for r in old]}})
    coll.insert_one(row)
    public_choices=[{k:c[k] for k in ('choice_id','label','input_type','minimum','maximum') if k in c} for c in rows]
    return {'clarification_id':cid,'decision_type':row['decision_type'],'reason_code':row['reason_code'],
            'question':question,'candidate_choices':public_choices,'original_query':query,'search_mode':mode,
            'parser_version':PARSER_VERSION,'plan_version':row['base_version'],'scope':owner['scope'],
            'workspace':owner['workspace'],'expires_at':row['expires_at'].isoformat(),
            'source_spans':[{'start':s.get('start'),'end':s.get('end')} for s in plan.source_spans if s.get('source_query',query)==query]}


def load_choice(actor,clarification_id,choice_id,*,mode,query,session_id,library_id=None,staff=False,value=None):
    """Called only inside fresh authorization. Neither IDs nor values are plans."""
    if staff and not library_id:raise HTTPException(404,'Search choice is unavailable.')
    cid=token(clarification_id);owner=identity(actor,library_id,staff);coll=collection()
    row=coll.find_one({'_id':'clarification:'+cid,**owner})
    if not row:raise HTTPException(404,'Search choice is unavailable. Submit the query again.')
    if row['expires_at'].replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc):
        raise HTTPException(410,'Search choice expired. Submit the query again.')
    if row.get('used') or row['parser_version']!=PARSER_VERSION or row['mode']!=mode or row['query']!=query or row['search_session_id']!=session_id:
        raise HTTPException(409,'Search choice changed. Submit the query again.')
    choice=next((c for c in row['choices'] if c['choice_id']==choice_id),None)
    if not choice:raise HTTPException(404,'Search choice is unavailable. Submit the query again.')
    if choice.get('input_type')=='number':
        try:numeric=float(value)
        except (ValueError,TypeError):raise HTTPException(422,'Enter a valid number.')
        if not math.isfinite(numeric) or not choice['minimum']<=numeric<=choice['maximum'] or choice.get('field')=='year' and not numeric.is_integer():
            raise HTTPException(422,'The number is outside the supported range.')
        value=f'{numeric:g}'
    elif choice.get('input_type')=='text':
        if not isinstance(value,str) or not value.strip() or len(value)>100:raise HTTPException(422,'Enter an author name of up to 100 characters.')
        value=value.strip()
    elif value is not None:raise HTTPException(422,'This choice does not accept an operand.')
    return row,choice,value


def transformer(row,choice,value):
    """Return an internal edit; re-use parser operands and preserve other fields."""
    def apply(plan,facets,capabilities):
        plan=deepcopy(plan);operation=choice['operation'];caps=capabilities or {}
        if operation not in ('unsupported_remove','literal') and any(c.get('support_status')=='UNSUPPORTED' for c in plan.constraint_candidates):
            raise HTTPException(422,'Remove the unsupported requirement before applying this choice.')
        if operation in ('bound','remove','format','subject'):
            field=choice.get('field','format' if operation=='format' else 'subject')
            affected={'subject','excluded_subject'} if field=='subject' else {field}
            # Check the untouched source with the accepted parser too. A bounds
            # decision can take priority over a second unfinished/ambiguous cue;
            # resolving the bounds must not silently authorize that other cue.
            original=parse_query(row['query'],facets,row['mode'])
            chars=list(row['query'])
            for candidate in original.constraint_candidates:
                if candidate['field'] in affected or candidate['field']=='connector':
                    for i in range(candidate['source_span_start'],min(candidate['source_span_end'],len(chars))):chars[i]=' '
            for span in original.source_spans:
                if span['kind']=='GRAMMATICAL_CONNECTOR':
                    for i in range(span['start'],min(span['end'],len(chars))):chars[i]=' '
            remaining=parse_query(''.join(chars).strip() or 'books',facets,row['mode'])
            if not executable(validate(remaining,caps)):
                raise HTTPException(422,'Another requirement still needs clarification. Edit the query and try again.')
        if operation=='complete':
            # The original unfinished text is parsed afresh with the operand.
            completed=parse_query(row['query']+' '+value,facets,row['mode'],row['filters'],row['omit'])
            field=choice['field']
            if not executable(validate(completed,caps)):raise HTTPException(422,'Complete the query before applying this choice.')
            if field=='author' and normalize(completed.author_text)!=normalize(value):raise HTTPException(422,'Enter only an author name.')
            names=('author_text',) if field=='author' else tuple(field+s for s in ('_min','_max','_min_exclusive','_max_exclusive'))
            for name in names:setattr(plan,name,getattr(completed,name))
        elif operation in ('bound','remove'):
            field=choice['field']
            if field not in ('rating','year','language','availability'):raise HTTPException(422,'Unsupported choice.')
            if operation=='bound' and caps.get(field) is False:raise HTTPException(409,'That filter is no longer available.')
            names=[field+'_min',field+'_max'] if field in ('rating','year') else [field]
            for name in names:setattr(plan,name,None)
            if operation=='bound':
                side=field+'_'+choice['side'];setattr(plan,side,choice['value']);setattr(plan,side+'_exclusive',choice['exclusive'])
        elif operation=='format':
            if choice['value'] not in caps.get('formats',['ONLINE','PHYSICAL','BOTH']):raise HTTPException(409,'That format is no longer supported.')
            parsed=parse_query({'ONLINE':'online only','PHYSICAL':'physical only','BOTH':'physical and online'}[choice['value']],facets)
            for name in ('formats','exclusive_formats','excluded_formats','physical_available_only'):setattr(plan,name,getattr(parsed,name))
        elif operation=='subject':
            vocab=FacetVocabulary(facets)
            for subject in choice['subjects']:
                canonical,_,_=vocab.resolve(subject,fuzzy=False)
                if not canonical or normalize(canonical)!=normalize(subject):raise HTTPException(409,'This subject is no longer available in the catalogue.')
            targets=set(map(normalize,choice['subjects']))
            plan.subjects=[s for s in plan.subjects if normalize(s) not in targets]
            plan.exclude_subjects=[s for s in plan.exclude_subjects if normalize(s) not in targets]
            plan.exclude_terms=[s for s in plan.exclude_terms if normalize(s) not in targets]
            if choice['action']=='include':plan.subjects.extend(choice['subjects'])
            if choice['action']=='exclude':plan.exclude_subjects.extend(choice['subjects'])
        elif operation=='ambiguous_rating':
            # Preserve the unambiguous fields by reparsing without ONLY the
            # parser-labelled ambiguous span, never stripping topic words.
            spans=[s for s in plan.source_spans if s.get('kind')=='AMBIGUOUS_NUMBER']
            spans+=plan.decision.get('relevant_source_spans',[])
            query=row['query'];chars=list(query)
            for span in spans:
                a,b=span.get('start',0),span.get('end',0)
                for i in range(max(0,a),min(b,len(chars))):chars[i]=' '
            parsed=parse_query(''.join(chars)+' rated at least '+str(choice['value']),facets,row['mode'],row['filters'],row['omit'])
            if not executable(validate(parsed,caps)):raise HTTPException(422,'Edit the query before applying this choice.')
            plan=parsed
        elif operation=='literal':plan=parse_query(row['query'],facets,'EXACT',row['filters'],row['omit'])
        elif operation=='unsupported_remove':
            # Unsupported spans are removed using the existing recognizer's
            # exact offsets. No invented page-count enforcement or soft promise.
            chars=list(row['query'])
            for candidate in plan.constraint_candidates:
                if candidate.get('support_status')=='UNSUPPORTED' and candidate['field'] in choice['fields']:
                    for i in range(candidate['source_span_start'],min(candidate['source_span_end'],len(chars))):chars[i]=' '
            plan=parse_query(''.join(chars).strip() or 'books',facets,row['mode'],row['filters'],row['omit'])
            if not executable(validate(plan,caps)):raise HTTPException(422,'Another requirement still needs editing before this query can run.')
        elif operation in ('correction_keep','correction_apply'):
            c=choice['correction'];canonical,_,_=FacetVocabulary(facets).resolve(c['from'])
            if canonical!=c['to']:raise HTTPException(409,'The correction is no longer available in this catalogue.')
            if operation=='correction_keep':
                if not row['filters'].get('subject'):plan.subjects=[s for s in plan.subjects if normalize(s)!=normalize(c['to'])]
                plan.semantic_text=' '.join(x for x in (plan.semantic_text,c['from']) if x)
                plan.unknown_subject=False
                if plan.intent=='BROWSE_CATEGORY':plan.intent='DISCOVER_TOPIC'
            plan.corrections=[]
        else:raise HTTPException(422,'Unsupported search choice.')
        # A resolved field must not carry the old rejected decision. Validation
        # runs again over the full final plan, including inherited constraints.
        plan.constraint_candidates=[c for c in plan.constraint_candidates if c.get('support_status') not in ('AMBIGUOUS','INCOMPLETE','UNSUPPORTED')]
        plan=validate(decide(plan),caps)
        if not executable(plan):raise HTTPException(422,'The remaining filters still conflict. Edit the query and try again.')
        return plan
    return apply


class ChoiceCommit:
    """One-use claim, fenced by the existing accepted-context version CAS.

    A claim is not consumption. Failed validation releases it unchanged; successful
    context writes record a receipt before the pending document is marked used.
    A crashed claimant is never stolen/replayed; the short pending TTL bounds it.
    """
    def __init__(self,row,claim):
        self.row=row;self.claim=claim;self.committed=False
        self.receipt={'clarification_id':row['_id'],'claim':claim}

    def check(self):
        now=datetime.now(timezone.utc)
        current=collection().find_one({'_id':self.row['_id'],'resolution_claim':self.claim,'used':{'$ne':True},
            'expires_at':{'$gt':now}}, {'expires_at':1})
        if not current:raise HTTPException(410,'Search choice expired or changed. Submit the query again.')
        return min(current['expires_at'].replace(tzinfo=timezone.utc),self.row['expires_at'].replace(tzinfo=timezone.utc))


@contextmanager
def reservation(row):
    coll=collection();claim=str(uuid4());now=datetime.now(timezone.utc)
    result=coll.update_one({'_id':row['_id'],'used':{'$ne':True},'resolution_claim':{'$exists':False},
                           'expires_at':{'$gt':now}}, {'$set':{'resolution_claim':claim}})
    if not result.modified_count:
        if row['expires_at'].replace(tzinfo=timezone.utc)<=now:raise HTTPException(410,'Search choice expired. Submit the query again.')
        raise HTTPException(409,'Search choice is already being applied or changed. Submit the query again.')
    guard=ChoiceCommit(row,claim)
    try:
        yield guard
    finally:
        # A network failure after a successful write must not make that choice
        # reusable. The receipt detects that outcome without rolling back a plan.
        sid=row.get('search_session_id')
        committed=guard.committed or bool(sid and coll.find_one({'_id':sid,'interaction_receipt':guard.receipt},{'_id':1}))
        update={'$unset':{'resolution_claim':''}}
        if committed:update['$set']={'used':True}
        coll.update_one({'_id':row['_id'],'resolution_claim':claim},update)
