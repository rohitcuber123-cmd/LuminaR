"""Phase-local validation; private source records never enter public reports."""
import hashlib
import json
import re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TMP=ROOT/'.scratch/cloze_v2_3'

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')

def baseline():
    from rag.services import document_knowledge as dk, knowledge_encoder, knowledge_quiz as q
    from rag.services.document_service import DocumentService
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('rag','backend','recommendation','frontend/src') for p in (ROOT/folder).rglob('*')
        if p.is_file() and p.suffix in {'.py','.tsx','.ts','.css'} and '__pycache__' not in str(p)}
    dump(ROOT/'reports/cloze_v2_3_baseline_hashes.json',hashes)
    processor=DocumentService.__new__(DocumentService)
    path=Path('C:/Users/balak/Downloads/CN UNIT-2 NOTES.docx.pdf')
    cn=processor.create_chunks('cn_v23',path.name,processor.extract_pdf(path))
    educational=json.loads((ROOT/'tests/fixtures/knowledge_educational.json').read_text(encoding='utf8'))
    for name,chunks in [('cn',cn),('educational',educational)]:
        model=dk.build(chunks,knowledge_encoder.encode)
        dump(TMP/f'{name}_chunks.json',chunks);dump(TMP/f'{name}_model.json',model.payload())
        dump(TMP/f'{name}_core_before.json',{kind:dk.generate(kind,model,name,{}) for kind in ('KEY_CONCEPTS','FLASHCARDS','EXTRACTIVE_SUMMARY','MIND_MAP')})
        dump(TMP/f'{name}_quiz_before.json',{kind:q.generate_from_knowledge(model,{'questionTypes':[kind],'questionCount':12}) for kind in ('mcq','matching','fill_blank')})
        print(name,'baseline saved',flush=True)

def ocr_fixture():
    import pymupdf as fitz
    from rag.services.document_service import DocumentService
    from rag.services import private_document_ocr as o, document_knowledge as dk
    chunks=json.loads((ROOT/'tests/fixtures/knowledge_educational.json').read_text(encoding='utf8'))[1:4]
    pdf=fitz.open()
    for chunk in chunks:
        text=fitz.open();page=text.new_page()
        assert page.insert_textbox(fitz.Rect(40,40,550,780),chunk['text'],fontsize=13)>=0
        scan=pdf.new_page();scan.insert_image(scan.rect,stream=page.get_pixmap(dpi=220).tobytes('png'));text.close()
    path=TMP/'scanned.pdf';pdf.save(path);pdf[0].get_pixmap(dpi=100).save(TMP/'scanned_review.png');pdf.close()
    processor=DocumentService.__new__(DocumentService);pages,stats=o.prepare(path,processor.extract_pdf(path))
    assert stats['ocr_pages']==3 and stats['native_pages']==0
    source=processor.create_chunks('scan_v23','scanned.pdf',pages)
    for chunk in source:chunk['extraction_method']='OCR'
    model=dk.build(source)
    dump(TMP/'ocr_chunks.json',source);dump(TMP/'ocr_model.json',model.payload())
    dump(ROOT/'reports/cloze_v2_3_ocr.json',{'pages':3,'stats':stats})
    print('Real image-only OCR fixture prepared.',flush=True)

def calibration():
    from collections import Counter
    import time
    from rag.services import document_knowledge as dk, knowledge_quiz as q, cloze_grading as g, knowledge_encoder, knowledge_cloze as c
    examples=[];preserved={};counts={};private=[]
    def add(name,item,answer,expected,category):
        examples.append({'document':name,'item':item,'answer':answer,'expected':expected,'category':category})
    for name in ('cn','educational','ocr'):
        model=dk.DocumentKnowledgeModel(**json.loads((TMP/f'{name}_model.json').read_text(encoding='utf8')))
        out=q.generate_from_knowledge(model,{'questionTypes':['fill_blank'],'questionCount':30})
        dump(TMP/f'{name}_cloze.json',out);counts[name]=len(out['questions'])
        for item in out['questions']:
            assert c.validate(item)
            canonical=item['canonicalAnswer']
            for category,answer in [('exact',canonical),('case',canonical.swapcase()),('spacing','  '+canonical.replace(' ','   ')+'  '),
                                    ('hyphen',canonical.replace(' ','-')),('article','the '+re.sub(r'^(?:a|an|the)\s+','',canonical,flags=re.I)),('punctuation',canonical+'!')]:
                if category=='hyphen' and item['blankType'] not in {'TERM','ENTITY'}:continue
                add(name,item,answer,'CORRECT',category)
            add(name,item,'purple elephant','INCORRECT','irrelevant')
            add(name,item,'not '+canonical,'INCORRECT','negated_phrase')
            if item['blankType'] in {'TERM','ENTITY'}:
                words=canonical.split();long=next((i for i,w in enumerate(words) if w.isalpha() and len(w)>=8),None)
                if long is not None:
                    words[long]=words[long][:3]+words[long][4:];add(name,item,' '.join(words),'CORRECT','minor_typo')
                other=next((x['canonicalAnswer'] for x in out['questions'] if x['blankType'] in {'TERM','ENTITY'} and x['canonicalAnswer']!=canonical),None)
                if other:add(name,item,other,'INCORRECT','wrong_related_term')
        if name!='ocr':
            core=json.loads((TMP/f'{name}_core_before.json').read_text(encoding='utf8'))
            old=json.loads((TMP/f'{name}_quiz_before.json').read_text(encoding='utf8'))
            preserved[name]={'core':core=={kind:dk.generate(kind,model,name,{}) for kind in core},
                'mcq':old['mcq']==q.generate_from_knowledge(model,{'questionTypes':['mcq'],'questionCount':12}),
                'matching':old['matching']==q.generate_from_knowledge(model,{'questionTypes':['matching'],'questionCount':12})}
    # Independently labelled narrow cases supplement generated document items.
    # They model explicit printed fixture evidence, not production synonym rules.
    def manual(canonical,kind,source=None):
        source=source or f'The specified value is {canonical}.'
        item={'id':'fixture_'+hashlib.sha256(source.encode()).hexdigest()[:16],'type':'fill_blank',
            'question':'Complete the source sentence: '+source.replace(canonical,'_____',1),
            'correctAnswer':canonical,'canonicalAnswer':canonical,'blankType':kind,'sourceExcerpt':source,
            'sourceFactId':'fact_'+hashlib.sha256(source.encode()).hexdigest()[:16],'subjectId':'fixture_subject','relationId':'fixture_relation',
            'evidenceUnitIds':['fixture_unit'],'sourceChunkIds':['fixture_chunk'],'pageStart':1,'pageEnd':1,
            'acceptedAliases':c.aliases(canonical,source),'conflictingTerms':['Selective Repeat','Go-Back-N','ALOHA','CSMA','CRC','checksum','transmission','transition']}
        assert c.validate(item)
        return item
    for canonical,correct,wrong in [('2T','2 T','T'),('2','2.0','20'),('5 ms','5 milliseconds','5 seconds'),
                                    ('5 seconds','5000 ms','5 milliseconds'),('50%','50.0 percent','5%'),('-2','-2.0','2')]:
        item=manual(canonical,g.answer_type(canonical))
        add('educational',item,correct,'CORRECT','numeric_equivalent');add('educational',item,wrong,'INCORRECT','numeric_wrong')
    for canonical,answer in [('5 ms','5 seconds'),('5 seconds','5 milliseconds'),('2T','2 seconds')]:
        add('educational',manual(canonical,g.answer_type(canonical)),answer,'INCORRECT','wrong_unit')
    for canonical,alias in [('Automatic Repeat reQuest (ARQ)','ARQ'),('acknowledgement (ACK)','ACK')]:
        item=manual(canonical,'TERM',f'{canonical} is an explicitly named term in these printed notes.')
        add('educational',item,alias,'CORRECT','safe_acronym');add('educational',item,canonical.split(' (')[0],'CORRECT','source_alias')
    for canonical,answer,expected in [('acknowledgement','acknowlegement','CORRECT'),('acknowledgement','acknowledgment','CORRECT'),
            ('transmission','transition','INCORRECT'),('Selective Repeat','Go-Back-N','INCORRECT'),('ALOHA','CSMA','INCORRECT'),('CRC','checksum','INCORRECT')]:
        add('educational',manual(canonical,'TERM'),answer,expected,'spelling_variant' if expected=='CORRECT' else 'wrong_related_term')
    phrase_cases=[
        ('controls the transmission rate','regulates how fast data can be sent','CORRECT'),
        ('controls sender rate so receiver is not overwhelmed','controls sender rate','PARTIAL'),
        ('allows multiple frames in transit','allows only one frame in transit','INCORRECT'),
        ('controls the transmission rate','does not control the transmission rate','INCORRECT'),
        ('waits for 5 seconds before transmission','waits for 5 milliseconds before transmission','INCORRECT'),
        ('removes the most recent value first','removes the latest stored item first','CORRECT'),
        ('divides memory into fixed size pages','splits memory into pages of equal size','CORRECT'),
        ('controls sender rate so receiver is not overwhelmed','regulates sender speed to protect the receiver','CORRECT'),
        ('allows multiple frames in transit','permits several frames to be in flight','CORRECT'),
        ('controls the transmission rate','purple elephant','INCORRECT'),
        ('controls sender rate so receiver is not overwhelmed','controls sender rate so receiver is overwhelmed','INCORRECT'),
        ('controls sender rate so receiver is not overwhelmed','controls receiver rate so sender is not overwhelmed','INCORRECT'),
        ('selects the process with the smallest execution time','selects the process','PARTIAL'),
        ('transfers outgoing email messages between mail servers','sends outgoing email between mail servers','CORRECT')]
    for canonical,answer,expected in phrase_cases:
        add('educational',manual(canonical,'DESCRIPTION',f'The described mechanism {canonical}.'),answer,expected,
            'correct_paraphrase' if expected=='CORRECT' else 'partial_phrase' if expected=='PARTIAL' else 'contradiction')
    # Warm the same local CPU encoder before timing; model load is reported separately.
    started=time.perf_counter();knowledge_encoder.encode(['CPU phrase grading preparation']);cold_ms=(time.perf_counter()-started)*1000
    results=[]
    for index,example in enumerate(examples):
        item=example['item'];actual=g.grade(item,example['answer'],knowledge_encoder.encode)
        row={'id':index,'document':example['document'],'item_id':item['id'],'answer_type':item['blankType'],
             'category':example['category'],'expected':example['expected'],'actual':actual['verdict'],'reason':actual['reason'],
             'answer_hash':hashlib.sha256(example['answer'].encode()).hexdigest(),'ms':actual['grading_ms']}
        results.append(row)
        if row['actual']!=row['expected']:
            private.append({**row,'canonical':item['canonicalAnswer'],'answer':example['answer'],'source':item['sourceExcerpt']})
    dump(TMP/'calibration_failures.json',private)
    dump(ROOT/'reports/cloze_v2_3_calibration.json',{'examples':len(results),'categories':dict(Counter(x['category'] for x in results)),
        'documents':dict(Counter(x['document'] for x in results)),'labels':'Generated identities use deterministic independently assigned variant labels; supplemental semantic cases are manually labelled source fixtures.',
        'development_only':True,'results':results})
    correct=[x for x in results if x['actual']=='CORRECT'];numeric=[x for x in results if x['category'] in {'numeric_equivalent','numeric_wrong','wrong_unit','contradiction'} and x['answer_type'] in {'NUMBER','NUMBER_WITH_UNIT'}]
    numeric_conflicts=[x for x in results if x['expected']=='INCORRECT' and (x['category'] in {'numeric_wrong','wrong_unit'} or x['reason']=='NUMERIC_CONFLICT')]
    quality={'examples':len(results),'correct_precision':sum(x['expected']=='CORRECT' for x in correct)/max(1,len(correct)),
        'overall_accuracy':sum(x['actual']==x['expected'] for x in results)/len(results),
        'term_false_accepts':sum(x['expected']=='INCORRECT' and x['actual']=='CORRECT' for x in results if x['answer_type'] in {'TERM','ENTITY'}),
        'numeric_accuracy':sum(x['actual']==x['expected'] for x in numeric)/max(1,len(numeric)),
        'numeric_case_count':len(numeric),'numeric_conflict_case_count':len(numeric_conflicts),
        'numeric_conflict_accuracy':sum(x['actual']=='INCORRECT' for x in numeric_conflicts)/max(1,len(numeric_conflicts)),
        'verdict_counts':dict(Counter(x['actual'] for x in results)),
        'failures':len(private),'generated_counts':counts,'preserved':preserved,'encoder_device':'cpu','qwen_calls':0,'cuda_calls':0,
        'cold_encoder_ms':round(cold_ms,2),'max_warm_grade_ms':max(x['ms'] for x in results)}
    dump(ROOT/'reports/cloze_v2_3_quality.json',quality)
    print(quality,flush=True)

if __name__=='__main__':
    globals()[sys.argv[1]]()
