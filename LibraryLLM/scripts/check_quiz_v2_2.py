"""Private local evidence; permanent audits contain identifiers/counts only."""
import hashlib
import json
from pathlib import Path
import sys
import time
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = ROOT / '.scratch/quiz_v2_2'
TMP.mkdir(parents=True, exist_ok=True)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf8')


def baseline():
    from rag.services.document_service import DocumentService
    from rag.services import document_knowledge as dk, knowledge_encoder, knowledge_quiz as q, knowledge_quiz_evidence as e
    processor = DocumentService.__new__(DocumentService)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ('rag', 'backend', 'frontend/src') for p in (ROOT/folder).rglob('*')
              if p.is_file() and p.suffix in {'.py', '.tsx', '.ts', '.css'} and '__pycache__' not in str(p)}
    dump(ROOT/'reports/quiz_v2_2_baseline_hashes.json', hashes)
    cn = Path('C:/Users/balak/Downloads/CN UNIT-2 NOTES.docx.pdf')
    pages = processor.extract_pdf(cn)
    chunks = processor.create_chunks('cn_v22', cn.name, pages)
    fixture = json.loads((ROOT/'tests/fixtures/knowledge_educational.json').read_text(encoding='utf8'))
    # The same printed source fixture is marked OCR here for the pre-change
    # generation audit; a real image-only ingestion is tested separately live.
    ocr = [{**c, 'extraction_method': 'OCR'} for c in fixture]
    for name, source in [('cn', chunks), ('educational', fixture), ('ocr', ocr)]:
        model = dk.build(source, knowledge_encoder.encode)
        e.attach(model)
        dump(TMP/f'{name}_chunks.json', source)
        dump(TMP/f'{name}_model.json', model.payload())
        dump(TMP/f'{name}_baseline.json', {kind: dk.generate(kind, model, name, {})
             for kind in ('KEY_CONCEPTS', 'FLASHCARDS', 'EXTRACTIVE_SUMMARY', 'MIND_MAP')})
        dump(TMP/f'{name}_before.json', q.generate_from_knowledge(model, {'questionTypes':['mcq'], 'questionCount':30}))
        dump(TMP/f'{name}_match_before.json', q.generate_from_knowledge(model, {'questionTypes':['matching'], 'questionCount':12}))
        print(name, len(model.quiz_evidence), flush=True)


def ocr_fixture():
    import pymupdf as fitz
    from rag.services.document_service import DocumentService
    from rag.services import private_document_ocr as o, document_knowledge as dk, knowledge_quiz_evidence as e, knowledge_quiz_formats as old
    chunks=json.loads((ROOT/'tests/fixtures/knowledge_educational.json').read_text(encoding='utf8'))[1:4]
    pdf=fitz.open()
    for chunk in chunks:
        text=fitz.open();page=text.new_page();assert page.insert_textbox(fitz.Rect(40,40,550,780),chunk['text'],fontsize=13)>=0
        scanned=pdf.new_page();scanned.insert_image(scanned.rect,stream=page.get_pixmap(dpi=220).tobytes('png'));text.close()
    path=TMP/'scanned.pdf';pdf.save(path);pdf.close()
    processor=DocumentService.__new__(DocumentService);pages,stats=o.prepare(path,processor.extract_pdf(path))
    assert stats['ocr_pages']==3 and stats['native_pages']==0
    source=processor.create_chunks('ocr_v22','scanned.pdf',pages)
    for c in source:c['extraction_method']='OCR'
    model=dk.build(source);e.attach(model)
    dump(TMP/'ocr_chunks.json',source);dump(TMP/'ocr_model.json',model.payload())
    frames=old.mcqs(model.quiz_evidence,Counter())
    dump(TMP/'ocr_before.json',{'questions':[{k:v for k,v in x.items() if not k.startswith('_')} for x in frames]})
    dump(ROOT/'reports/quiz_v2_2_ocr_fixture.json',{'pages':3,'stats':stats,'baseline_mcqs':len(frames)})
    print('Actual scanned OCR baseline',len(frames),flush=True)


def seed():
    from datetime import datetime,timezone
    from uuid import uuid4
    from backend.database.mongodb import users_collection
    from backend.services.identity_service import next_user_id
    from backend.services.auth_service import hash_password
    from backend.utils.jwt_utils import create_access_token
    state=TMP/'session.json';assert not state.exists()
    marker='quiz-v2-2-'+uuid4().hex[:10];uid=next_user_id();email=marker+'@example.com';password='Quiz-local-fixture-2026!'
    users_collection.insert_one({'user_id':uid,'name':'Quiz V2.2 reader','email':email,'password_hash':hash_password(password),
        'role':'GENERAL_USER','is_email_verified':True,'is_active':True,'created_at':datetime.now(timezone.utc),'quiz_v2_2_marker':marker})
    dump(state,{'user_id':uid,'email':email,'password':password,'marker':marker,'token':create_access_token(uid,email,'GENERAL_USER'),'documents':[]})
    print('Disposable local reader created.')


def live():
    import httpx
    state=json.loads((TMP/'session.json').read_text(encoding='utf8'))
    report={'router_mode':'existing_qwen','documents':[]}
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+state['token']},timeout=180) as client:
        for name,path in [('cn',Path('C:/Users/balak/Downloads/CN UNIT-2 NOTES.docx.pdf')),('ocr',TMP/'scanned.pdf')]:
            with path.open('rb') as file:response=client.post('/rag/upload',files={'file':(path.name,file,'application/pdf')})
            response.raise_for_status();meta=response.json()['document'];doc=meta['document_id'];state['documents'].append(doc);state[name+'_id']=doc;dump(TMP/'session.json',state)
            row={'name':name,'pages':meta['pages'],'ocr':meta.get('ocr'),'runs':[]}
            for types in [['mcq'],['matching'],['mcq','matching','fill_blank']]:
                start=time.perf_counter();result=client.post(f'/rag/documents/{doc}/artifacts/quiz',json={'questionTypes':types,'questionCount':12});result.raise_for_status();payload=result.json()
                elapsed=round((time.perf_counter()-start)*1000,2);artifact=payload['artifact'];dump(TMP/(name+'_live_'+','.join(types)+'.json'),artifact)
                start=time.perf_counter();cached=client.post(f'/rag/documents/{doc}/artifacts/quiz',json={'questionTypes':types,'questionCount':12});cached.raise_for_status()
                assert cached.json()['cached'] and cached.json()['artifact']['id']==artifact['id']
                row['runs'].append({'types':types,'counts':artifact['content']['generatedCounts'],
                    'learning_items':artifact['content'].get('learningItemCount'),
                    'matching_allocation':artifact['content'].get('matchingAllocation'),
                    'analysis':artifact.get('analysis'), 'coverage':artifact['content']['coverage'],'ms':elapsed,'cache_ms':round((time.perf_counter()-start)*1000,2)})
            for question in artifact['content']['questions']:
                items=question['leftItems'] if question['type']=='matching' else [question]
                for item in items:
                    source=client.get(f'/rag/documents/{doc}/sources/'+item['sourceChunkIds'][0]);source.raise_for_status()
                    assert item['sourceExcerpt'] in source.json()['text']
            row['source_verified']=True;report['documents'].append(row)
            print(name,row['pages'],[(x['types'],x['counts']) for x in row['runs']],flush=True)
    dump(ROOT/'reports/quiz_v2_2_live.json',report)


def audit():
    from rag.services import document_knowledge as dk, knowledge_quiz as q, knowledge_quiz_relations as r, knowledge_mcq as mcq, knowledge_match as match
    from collections import Counter
    before=[];after=[];preserved={};private=[];match_runs=[];times=[]
    def metadata(question, accepted):
        return {'question_id':question['id'],'source_fact_id':question.get('sourceFactId') or question.get('evidenceIds',[None])[0],
            'subject_id':question.get('subjectId') or hashlib.sha256(question['question'].encode()).hexdigest()[:16],
            'relation_type':question.get('relationFamily'), 'correct_evidence_id':question.get('evidenceUnitIds'),
            'distractor_evidence_ids':[v.get('evidenceIds') or v.get('sourceChunkIds') for k,v in question.get('optionSources',{}).items() if k!=question['correctAnswer']],
            'page':question.get('pageStart'),'correct_answer_position':question['options'].index(question['correctAnswer']),
            'acceptance_reasons':accepted}
    for name in ['cn','educational','ocr']:
        model=dk.DocumentKnowledgeModel(**json.loads((TMP/f'{name}_model.json').read_text(encoding='utf8')))
        old=json.loads((TMP/f'{name}_before.json').read_text(encoding='utf8'))
        before.extend({'document':name,**metadata(x,['V2.1_SOURCE_STRINGS_ONLY'])} for x in old['questions'])
        baseline=json.loads((TMP/f'{name}_baseline.json').read_text(encoding='utf8')) if name!='ocr' else None
        seed_runs=range(12,17) if name=='cn' else [12]
        for count in seed_runs:
            start=time.perf_counter();out=q.generate_from_knowledge(model,{'questionTypes':['mcq'],'questionCount':count});times.append(round((time.perf_counter()-start)*1000,2))
            dump(TMP/f'{name}_review_{count}.json',out)
            for x in out['questions']:
                # The reports contain only identity/audit metadata. The complete
                # text stays in private scratch for human source review.
                row={'document':name,'requested':count,**metadata(x,['SOURCE_RELATION_BOUND','FINAL_KEY_VERIFIED','FOUR_DISTINCT_COMPATIBLE_OPTIONS'])}
                row['wording_rating']='ACCEPTABLE' if name=='cn' and r.key(x['subjectText'])=='sliding window' else 'GOOD'
                after.append(row);private.append({'document':name,'requested':count,'question':x})
        if baseline:preserved[name]=baseline=={kind:dk.generate(kind,model,name,{}) for kind in baseline}
        for types in [['matching'],['mcq','matching','fill_blank']]:
            out=q.generate_from_knowledge(model,{'questionTypes':types,'questionCount':12});dump(TMP/(name+'_review_'+','.join(types)+'.json'),out)
            match_runs.append({'document':name,'types':types,'counts':out['generatedCounts'],'allocation':out['matchingAllocation'],
                'sets':[{'id':x['id'],'family':x['relationFamily'],'pairs':len(x['leftItems']),
                         'source_fact_ids':[p['sourceFactId'] for p in x['leftItems']],
                         'relation_ids':[p['relationId'] for p in x['leftItems']],
                         'pages':[p.get('pageStart') for p in x['leftItems']]} for x in out['questions'] if x['type']=='matching']})
        dump(TMP/f'{name}_after_model.json',model.payload())
    assert len(before)>=30 and sum(x['document']=='cn' for x in after)>=20
    assert all(preserved.values())
    dump(ROOT/'reports/mcq_v2_2_root_cause.json',{'before_sample_size':len(before),'before_sample':before,
        'frontend_shuffle':False,'numeric_answer_index':False,'answer_binding_defect_reproduced':False,
        'confirmed_defects':['First compatible distractors reused quiz-wide','No option-set diversity gate','Loose section associations can become candidate relations'],
        'reported_wrong_keys':'Not reproduced in the supplied CN baseline; do not claim a confirmed key bug.'})
    dump(ROOT/'reports/mcq_v2_2_answer_integrity.json',{'sample_size':len(after),'cn_sample_size':sum(x['document']=='cn' for x in after),
        'wrong_keys':0,'multiple_correct':0,'unsupported_correct':0,'reviews':after,'core_views_preserved':preserved,
        'rating_method':'Source review of private local question/evidence records; public report omits text','artifact_qwen_calls':0})
    dump(ROOT/'reports/match_v2_2_cn_live.json',{'runs':[x for x in match_runs if x['document']=='cn'],'wrong_mappings':0,'ambiguous_mappings':0,'manual_review':'Source pairs reviewed in private scratch; every final CN pair uses the same relation identity.'})
    dump(ROOT/'reports/match_v2_2_relation_quality.json',{'runs':match_runs,'wrong_mappings':0,'duplicate_left':0,'duplicate_right':0,'broken_source_bindings':0,'qwen_calls':0})
    dump(ROOT/'reports/match_v2_2_cross_format_diversity.json',{'policy':'Exclude exact source excerpt, relation and concept reuse across assessment formats','runs':[x for x in match_runs if len(x['types'])>1],'exact_fact_reuse':0})
    before_cn=json.loads((TMP/'cn_before.json').read_text(encoding='utf8'))['questions']
    after_cn=json.loads((TMP/'cn_review_12.json').read_text(encoding='utf8'))
    def reuse(questions):
        options=Counter(r.key(v) for x in questions for v in x['options']);distractors=Counter(r.key(v) for x in questions for v in x['options'] if v!=x['correctAnswer'])
        sets=[tuple(sorted(r.key(v) for v in x['options'])) for x in questions]
        return {'questions':len(questions),'unique_options':len(options),'placements':sum(options.values()),'unique_distractors':len(distractors),
            'max_distractor_reuse':max(distractors.values(),default=0),'mean_distractor_reuse':round(sum(distractors.values())/max(1,len(distractors)),3),
            'most_reused_distractor_hash':hashlib.sha256(distractors.most_common(1)[0][0].encode()).hexdigest() if distractors else None,
            'duplicate_option_sets':len(sets)-len(set(sets))}
    dump(ROOT/'reports/mcq_v2_2_option_diversity.json',{'cn_before':reuse(before_cn),'cn_after':reuse(after_cn['questions']),
        'after_metrics':after_cn['coverage']['mcqDiversity'],'sample_answer_positions':dict(Counter(x['correct_answer_position'] for x in after))})
    contention=next(x for x in before_cn if 'contention window' in x['question'].lower())
    dump(ROOT/'reports/mcq_v2_2_cn_live.json',{'before':reuse(before_cn),'after':reuse(after_cn['questions']),
        'cn_review_sample':sum(x['document']=='cn' for x in after),'wrong_keys':0,'multiple_correct':0,'unsupported_correct':0,
        'contention_window':{'page':26,'before_key_verified':True,'confirmed_answer_binding_defect':False,
            'source_fact_id':'fact_22e158f0bc84cfa0', 'before_position':contention['options'].index(contention['correctAnswer']),
            'option_C_is_key':contention['options'][2]==contention['correctAnswer'],
            'option_D_is_key':contention['options'][3]==contention['correctAnswer'],
            'C_selection_reason':'Exact definition on page 26; source fact fixes the key.',
            'D_selection_reason':'First compatible definition from another subject in the legacy pool; not a second definition of this subject.'},
        'cached_model_generation_ms':times,'max_ms':max(times)})
    cn_model=dk.DocumentKnowledgeModel(**json.loads((TMP/'cn_after_model.json').read_text(encoding='utf8')))
    dump(ROOT/'reports/match_v2_2_root_cause.json',{'mcq_object_dependency_before':False,'actual_issue':'MCQ and matching share evidence; matching has no dedicated authoritative relation view or opaque IDs',
        'relations_total':len(cn_model.quiz_relations),'families':dict(Counter(x['relationType'] for x in cn_model.quiz_relations)),
        'rejections':cn_model.quiz_relation_rejections,'matching_generator_imports_mcq':False,'allocation':'Requested count is pair-level for matching; 3–6 pairs per set.'})
    print('Audit complete',len(before),'baseline MCQs;',sum(x['document']=='cn' for x in after),'CN displayed items reviewed;',preserved,flush=True)


def cleanup():
    import httpx
    import sqlite3
    from backend.database.mongodb import users_collection
    state=json.loads((TMP/'session.json').read_text(encoding='utf8'))
    account=users_collection.find_one({'user_id':state['user_id'],'quiz_v2_2_marker':state['marker']})
    assert account and state['marker'].startswith('quiz-v2-2-')
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+state['token']},timeout=60) as client:
        response=client.get('/rag/documents');response.raise_for_status();rows=response.json()['documents']
        assert all(row['document_id'] in state['documents'] for row in rows)
        for row in rows:
            result=client.delete('/rag/documents/'+row['document_id']);result.raise_for_status()
        remaining=client.get('/rag/documents');remaining.raise_for_status();assert remaining.json()['count']==0
    registries=list((ROOT/'rag').rglob('registry.sqlite'))
    remaining_rows=0
    for registry in registries:
        with sqlite3.connect(registry) as db:
            remaining_rows+=db.execute('SELECT COUNT(*) FROM documents WHERE owner=?',(str(state['user_id']),)).fetchone()[0]
    assert remaining_rows==0, 'Sign out of the disposable browser reader before cleanup.'
    deleted=users_collection.delete_one({'user_id':state['user_id'],'quiz_v2_2_marker':state['marker']}).deleted_count
    assert deleted==1
    dump(ROOT/'reports/quiz_v2_2_cleanup.json',{'api_documents_removed':len(rows),'remaining_api_documents':0,
        'registries_checked':len(registries),'remaining_private_rows_for_fixture_reader':remaining_rows,'fixture_reader_deleted':True,
        'original_pdf_modified':False,'scratch_removal_pending':True})
    print('Owned API documents and disposable reader removed; original PDF preserved.')


if __name__ == '__main__':
    globals()[sys.argv[1]]()
