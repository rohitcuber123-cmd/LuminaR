"""V11 accepted-source/choice lifecycle over a persistence-ready CAS interface."""
from dataclasses import asdict
from copy import deepcopy
from uuid import uuid4
from datetime import datetime,timezone
import time,re
from fastapi import HTTPException
from search.smart_preview import compile_query,digest,VERSION
from search.query_confidence import executable

FIELD_KEYS={'author':['author_text'],'subject':['subjects','include_terms'],'rating':['rating_min','rating_max','rating_min_exclusive','rating_max_exclusive'],
    'year':['year_min','year_max','year_min_exclusive','year_max_exclusive'],'language':['language'],'format':['formats','exclusive_formats','excluded_formats'],
    'excluded_format':['excluded_formats'],'excluded_subject':['exclude_subjects'],'exclude':['exclude_terms'],'sort':['sort'],'title':['title_text'],'literal':['exact_text'],
    'availability':['availability','physical_available_only']}


class PreviewService:
    def __init__(self,store,*,clock=time.time):self.store=store;self.clock=clock

    @staticmethod
    def owner(actor,library_id,staff,mode):
        return dict(actor=str(actor['sub']),login_session=actor.get('sid'),library_id=library_id,
            workspace='STAFF' if staff else 'PATRON' if library_id else 'GLOBAL',mode=mode,feature=VERSION)

    def operations(self,plan,facets,capabilities=None):
        ops={}
        def issue(kind,label,**data):
            key=str(uuid4());ops[key]=dict(kind=kind,label=label,**data)
        ir=plan.decision.get('query_ir_contract',{})
        if plan.mode=='SMART':
            for missing in plan.decision.get('v11_missing_requirements',[]):
                issue('complete','Choose required format',field='format',custom_format=missing,input_type='select',options=(capabilities or {}).get('formats',['ONLINE','PHYSICAL','BOTH']))
            for r in ir.get('requirements',[]):
                if r['ownership']!='MANDATORY':continue
                if r['field'] in FIELD_KEYS and r['state'] in ('OMITTED_REQUIRED_VALUE','EXPLICITLY_EMPTY','PLACEHOLDER_AWAITING_COMPLETION'):
                    issue('complete','Complete '+r['field'].replace('_',' '),requirement_id=r['requirement_id'],field=r['field'],input_type='number' if r['field'] in ('rating','year') else 'text')
            for field in sorted({r['field'] for r in ir.get('requirements',[]) if r['field'] in FIELD_KEYS and r['ownership']=='MANDATORY'}):
                issue('remove','Remove '+field.replace('_',' '),field=field)
            for operation,label in [('correction_apply','Apply correction'),('correction_keep','Keep my wording')]:
                try:
                    from scratch.search_architecture_v10.recompilation import issue_correction
                    issue_correction(plan,operation,1)
                except (ValueError,KeyError):continue
                issue(operation,label)
            if executable(plan):
                for field,label,options in [('author','Add author',None),('rating','Set minimum rating',None),
                    ('format','Require format',['ONLINE','PHYSICAL','BOTH']),('subject','Add category',list(facets)),
                    ('sort','Change sort',['RELEVANCE','RATING','NEWEST','TITLE'])]:
                    issue('add',label,field=field,input_type='number' if field=='rating' else 'select' if options is not None else 'text',options=options)
        return ops

    @staticmethod
    def edit(old,op,value):
        from scratch.search_architecture_v10 import parser
        from scratch.search_architecture_v10.recompilation import issue_completion,issue_correction,issue_remove
        plan=parser.QueryPlan(**old['plan']);kind=op['kind'];filters=deepcopy(old.get('filters',{}))
        if kind=='complete' and op.get('custom_format'):
            if value not in op['options']:raise ValueError('Choose a supported format.')
            missing=op['custom_format'];a,b=missing['span'];source=old['accepted_source']
            if source[a:b]!=missing['text']:raise ValueError('The source-owned format slot changed.')
            replacement='require '+('both online and physical' if value=='BOTH' else value.lower())+' format'
            if source[:a].strip() and source[:a].rstrip()[-1] not in ';.!?':replacement='; '+replacement
            source=source[:a]+replacement+source[b:]
        elif kind=='complete':source=issue_completion(plan,op['requirement_id'],value,old['version']).expected_query
        elif kind.startswith('correction_'):source=issue_correction(plan,kind,old['version']).expected_query
        elif kind=='remove':
            field=op['field'];ir=plan.decision['query_ir_contract'];rr=[r for r in ir['requirements'] if r['field']==field and r['ownership']=='MANDATORY']
            if any(r['provenance'].get('origin')=='TRUSTED_CONTROL' for r in rr):
                for key in {'subject':['subject'],'format':['format'],'author':['author'],'rating':['rating_min','rating_max'],
                    'year':['year_min','year_max'],'sort':['sort'],'language':['language'],'availability':['availability']}.get(field,[]):filters.pop(key,None)
                rr=[r for r in rr if r['provenance'].get('origin')!='TRUSTED_CONTROL']
            source=issue_remove(plan,field,old['version']).expected_query if rr else old['accepted_source']
        elif kind=='add':
            value=str(value or '').strip()
            if not value or len(value)>100 or re.search(r'["“”\r\n;]',value):raise ValueError('Enter one valid filter value.')
            field=op['field']
            if op.get('options') is not None and value not in op['options']:raise ValueError('Choose an offered value.')
            if field=='author':suffix='by "'+value+'"'
            elif field=='subject':suffix='include subject "'+value+'"'
            elif field=='format':suffix='require '+('both online and physical' if value=='BOTH' else value.lower())+' format'
            elif field=='sort':suffix={'TITLE':'sort by title','RATING':'sort by rating','NEWEST':'sort newest first','RELEVANCE':'sort by relevance'}[value]
            else:
                if not re.fullmatch(r'\d(?:\.\d+)?',value) or not 0<=float(value)<=5:raise ValueError('Rating must be from 0 to 5.')
                suffix='rating at least '+value
            source=old['accepted_source']+'; '+suffix
        else:raise ValueError('Unsupported search operation.')
        if len(source)>500:raise ValueError('The accepted search exceeds 500 characters. Remove a filter or shorten the query.')
        return source,filters

    def prepare(self,request,actor,facets,capabilities):
        now=self.clock();owner=self.owner(actor,request.library_id,request.staff,request.mode);old=None
        if request.state_id:
            old=self.store.get(str(request.state_id),owner,now)
            if request.version!=old['version'] or old['parser_version']!=VERSION:raise HTTPException(409,'Search changed. Refresh the accepted query before retrying.')
            if digest(old['plan'])!=old['plan_digest'] or digest(old['accepted_source'])!=old['source_digest']:raise HTTPException(409,'Stored search evidence changed.')
        if request.operation_id:
            if not old:raise HTTPException(409,'Search state is required for this operation.')
            op=old['operations'].get(str(request.operation_id))
            if op is None:raise HTTPException(409,'This operation was already used or is unavailable.')
            if request.query!=old['accepted_source']:raise HTTPException(409,'Search source changed. Submit it as a new search.')
            source,filters=self.edit(old,op,request.value)
        else:source=request.query;filters=request.filters.model_dump(exclude_none=True) if request.filters else {}
        plan,accepted,provenance=compile_query(source,facets,mode=request.mode,filters=filters,capabilities=capabilities)
        # An edit cannot silently discard unrelated mandatory native operands.
        if old and request.operation_id:
            old_plan=old['plan'];edited=op.get('field');allowed=set(FIELD_KEYS.get(edited,[]))
            if op['kind']=='complete':allowed.update(FIELD_KEYS.get(op['field'],[]))
            elif op['kind'].startswith('correction_'):allowed.update(FIELD_KEYS['subject'])
            for names in FIELD_KEYS.values():
                for key in names:
                    if key not in allowed and getattr(plan,key)!=old_plan[key]:raise HTTPException(409,'This edit would change another required filter. Edit the full query instead.')
            if op['kind']=='add' and edited in ('subject','format'):
                for key in FIELD_KEYS[edited]:
                    prior=old_plan[key];current=getattr(plan,key)
                    if isinstance(prior,list) and not set(prior).issubset(set(current)):raise HTTPException(409,'Adding a filter lost an earlier selection.')
            if op['kind']=='add' and edited=='author' and old_plan['author_text'] and old_plan['author_text']!=plan.author_text:
                raise HTTPException(409,'Remove the earlier author before replacing it.')
            if op['kind'] in ('add','remove','complete'):
                topic=old_plan.get('semantic_text')
                if topic and op.get('custom_format'):
                    missing_text=re.sub(r'^(?:with|require)\s+','',op['custom_format']['text'],flags=re.I)
                    topic=re.sub(re.escape(missing_text),'',topic,flags=re.I).strip(' ;')
                if topic and topic.casefold() not in str(plan.semantic_text or '').casefold():raise HTTPException(409,'This edit would lose the search topic. Edit the full query instead.')
                if old_plan.get('soft_preference')!=plan.soft_preference:raise HTTPException(409,'This edit would change another preference. Edit the full query instead.')
        data=asdict(plan);ir=data['decision'].get('query_ir_contract',{})
        new_search=old is not None and not request.operation_id and source!=old['accepted_source']
        row=dict(_id=old['_id'] if old else str(uuid4()),owner=owner,version=old['version']+1 if old else 1,parser_version=VERSION,
            original_source=old['original_source'] if old and not new_search else request.query,submitted_source=source,accepted_source=accepted,
            source_digest=digest(accepted),ir_digest=digest(ir),plan_digest=digest(data),plan=data,filters=filters,
            provenance=[*(old.get('provenance',[]) if old and not new_search else []),*provenance,
                *([dict(kind='SERVER_ISSUED_EDIT',operation=op['kind'],prior_version=old['version'],original_source=old['accepted_source'],accepted_source=accepted)] if request.operation_id else [])],
            created_at=old['created_at'] if old else now,expires_at=min(now+900,(old['created_at'] if old else now)+3600),operations=self.operations(plan,facets,capabilities))
        return plan,row,old

    def commit(self,row,old):
        now=self.clock()
        if row['expires_at']<=now:raise HTTPException(410,'Search expired before it completed. Submit it again.')
        if old:self.store.replace(old,row,now)
        else:self.store.create(row)

    @staticmethod
    def response(row,result):
        plan=row['plan'];interpretation=deepcopy(result.get('interpretation',{}))
        is_executable=plan['decision'].get('decision_type','EXECUTABLE') in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE')
        if not is_executable:interpretation['chips']=[]
        else:
            for chip in interpretation.get('chips',[]):
                if chip['key']=='format' and plan['exclusive_formats']:
                    chip['label']='Format: '+('Online only' if plan['exclusive_formats']==['ONLINE'] else 'Physical only')
            interpretation.setdefault('chips',[]).extend(dict(key='excluded_format',label='Exclude format: '+x.title()) for x in plan['excluded_formats'] if not plan['exclusive_formats'])
        return dict(result,interpretation=interpretation,preview=dict(version=VERSION,registry='V11-native-capabilities-v3',
            state_id=row['_id'],accepted_plan_version=row['version'],original_query=row['original_source'],accepted_query=row['accepted_source'],
            source_digest=row['source_digest'],ir_digest=row['ir_digest'],parser_version=VERSION,mode=plan['mode'],
            expires_at=datetime.fromtimestamp(row['expires_at'],timezone.utc).isoformat(),operations=[dict(operation_id=k,**v) for k,v in row['operations'].items()],
            provenance=row['provenance'],decision=plan['decision']['decision_type'],message=plan['decision'].get('safe_public_message',''),
            advisory=plan.get('soft_preference'),source_bound=True))
