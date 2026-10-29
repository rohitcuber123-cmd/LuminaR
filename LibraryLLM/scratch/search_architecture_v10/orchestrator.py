"""Disabled semantic-first integration boundary; read-only dependencies only.

Not imported by production. A backend must establish ScopeContext after fresh
authorization. It must not construct one from interpreter/model/user claims.
The candidate set is bounded: totals/pagination describe only that set.
"""
from dataclasses import dataclass, asdict
from copy import deepcopy
import time
from .parser import parse_query,validate,executable
from .capabilities import check,SCOPES
from .contract import digest


@dataclass(frozen=True)
class ScopeContext:
    scope: str
    actor_id: str
    login_session: str
    library_id: str | None
    membership_version: str
    staff: bool=False

    def __post_init__(self):
        if self.scope not in SCOPES:raise ValueError('Unknown scope')
        if not self.actor_id or not self.login_session:raise ValueError('Backend identity required')
        if (self.scope=='GLOBAL') != (self.library_id is None):raise ValueError('Scope/library mismatch')
        if self.scope!='GLOBAL' and self.staff!=self.scope.endswith('_STAFF'):raise ValueError('Workspace mismatch')


class ProviderFailure(RuntimeError):pass


class ReadOnlyNativeAdapter:
    """Inject existing provider, authoritative hydration, auth and serializer.

    A fixture provider with fixed IDs verifies transport only. Online entitlement
    must be hydrated for positive AND negative predicates. Hydration must return
    tenant-local ownership; linked global records alone are never tenant records.
    """
    def __init__(self,*,authorize,retrieve,hydrate,serialize,entitlements=lambda ctx:set(),candidate_bound=1000):
        self.authorize=authorize;self.retrieve=retrieve;self.hydrate=hydrate;self.serialize=serialize
        self.entitlements=entitlements;self.candidate_bound=candidate_bound

    def execute(self,plan,context,offset,limit):
        from search.query_plan import matches,sort_books
        if not self.authorize(context):raise PermissionError('Library resource unavailable')
        snapshot=digest(asdict(plan));source=deepcopy(plan)
        try:
            # Preferences already have a native rerank query. Use them in the
            # embedding query too, without manufacturing a metadata predicate.
            text=source.semantic_text
            preferences=[r['source_text'] for r in source.decision.get('query_ir_contract',{}).get('requirements',[]) if r['ownership']=='ADVISORY']
            if preferences:text='; '.join([*( [text] if text else []),*dict.fromkeys(preferences)])
            candidates=list(self.retrieve(context=context,semantic_text=text,plan=deepcopy(source),
                                          limit=self.candidate_bound))
            if len(candidates)>self.candidate_bound:raise ProviderFailure('Candidate bound violated')
            rows=list(self.hydrate(context=context,candidates=candidates))
            if len(rows)>self.candidate_bound:raise ProviderFailure('Hydration bound violated')
            if not self.authorize(context):raise PermissionError('Library resource unavailable')
            online=set(self.entitlements(context)) if context.scope=='GLOBAL' else set()
            canonical=[]
            candidate_ids=set(candidates)
            for row in rows:
                key=row.get('work_id') if context.scope=='GLOBAL' else row.get('library_book_id')
                if key not in candidate_ids:raise ProviderFailure('Hydration introduced an unrequested record')
                if context.scope!='GLOBAL' and row.get('library_id')!=context.library_id:
                    raise ProviderFailure('Foreign institution record in hydration')
                item=dict(row)
                if context.scope=='GLOBAL':item.update(has_online=key in online,has_physical=False)
                if matches(source,item):canonical.append(item)
            canonical=sort_books(canonical,source)
            # Serialize only accepted rows, then check serialized fields again.
            page=list(self.serialize(context=context,rows=deepcopy(canonical[offset:offset+limit])))
            allowed={r.get('work_id') if context.scope=='GLOBAL' else r.get('library_book_id') for r in canonical[offset:offset+limit]}
            for r in page:
                key=r.get('work_id') if context.scope=='GLOBAL' else r.get('library_book_id')
                if key not in allowed or not matches(source,r):raise ProviderFailure('Serialization changed result constraints')
                if context.scope!='GLOBAL' and r.get('library_id')!=context.library_id:raise ProviderFailure('Serialization changed scope')
            if digest(asdict(plan))!=snapshot:raise ProviderFailure('Plan changed during retrieval')
            return dict(results=page,total_ranked_candidates=len(canonical),offset=offset,limit=limit,
                        has_more=offset+limit<len(canonical),candidate_bound=self.candidate_bound,
                        completeness='BOUNDED_CANDIDATE_SET_ONLY',semantic_provider='INJECTED_UNVERIFIED')
        except PermissionError:raise
        except Exception as e:
            if isinstance(e,ProviderFailure):raise
            raise ProviderFailure('Read-only provider failed; no broader fallback') from e


def clarification(plan):
    blob=plan.decision.get('query_ir_contract',{})
    prompts={'author':'Which author?','title':'Which title?','literal':'Which title?',
             'rating':'Which rating cutoff and direction?','format':'Which format?',
             'sort':'Which sort field?','subject':'Which category, and should it be included or excluded?',
             'year':'Which publication year?','language':'Which language?',
             'page_count':'Which page count? Page-count filtering is unavailable.'}
    unresolved=[r for r in blob.get('requirements',[]) if r['ownership']=='MANDATORY' and r['state']!='EXPLICITLY_SUPPLIED']
    return [dict(requirement_id=r['requirement_id'],field=r['field'],source_span=r['source_span'],
                 source_text=r['source_text'],prompt=prompts.get(r['field'],'Which alternative or required relationship do you mean?'))
            for r in unresolved]


class SmartSearchOrchestrator:
    disabled=True
    def __init__(self,adapter,*,fixture_enabled=False):self.adapter=adapter;self.fixture_enabled=fixture_enabled

    def search(self,query,context,*,facets=(),mode='SMART',filters=None,omit=(),offset=0,limit=10):
        if not self.fixture_enabled:raise RuntimeError('V10 integration is disabled')
        if type(offset) is not int or type(limit) is not int or offset<0 or not 1<=limit<=100:raise ValueError('Invalid pagination')
        if not self.adapter.authorize(context):raise PermissionError('Library resource unavailable')
        start=time.perf_counter()
        plan=check(parse_query(query,facets,mode,filters,omit),context.scope)
        kind=plan.decision['decision_type']
        if not executable(plan):
            return dict(path='UNSUPPORTED' if kind=='UNSUPPORTED' else 'CLARIFICATION',decision=kind,
                        results=[],clarification=clarification(plan),interpretation=asdict(plan),
                        reason=plan.decision.get('safe_public_message',''))
        hard=any(r['channel']=='B_STRUCTURED' for r in plan.decision.get('query_intent',{}).get('units',[]))
        result=self.adapter.execute(plan,context,offset,limit)
        return dict(result,path='STRUCTURED_SEMANTIC' if hard else 'SEMANTIC',decision=kind,
                    interpretation=asdict(plan),timing_ms=dict(component_total=(time.perf_counter()-start)*1000))
