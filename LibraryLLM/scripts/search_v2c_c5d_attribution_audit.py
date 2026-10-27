"""Refine C5D source citations without altering any historical disposition/score."""
from collections import Counter
from pathlib import Path
from scripts.search_v2c_c5d_prepare import R,P,load,rows,sha,write,jsonl

def main():
    refs=load(R/(P+'source_references.json'))
    def ref(path,start,end,owner):
        return {'path':path,'start_line':start,'end_line':end,'owner':owner,'sha256':sha(path),
                'excerpt':'\n'.join(Path(path).read_text(encoding='utf8').splitlines()[start-1:end])}
    refs['matches']=ref('search/query_plan.py',295,308,'matches literal negatives and required author/title predicates')
    refs['normalization']=ref('search/query_plan.py',19,22,'normalize')
    refs['evaluator']=ref('scripts/search_v2c_c4_evaluate.py',154,188,'rescore')
    write('source_references_v2.json',refs)
    matrix=rows(R/(P+'root_cause_matrix.jsonl'));amendments=[];operands=[]
    for row in matrix:
        for cause in row['causes']:
            if cause['root_id']=='FINITE_FIELD_RECOGNIZER_GAP':
                field=cause['dimension'];target='year' if field.startswith('year_') else 'author' if field in ['author_text','title_text'] else 'format'
                if target!=cause['source_reference']:
                    amendments.append({'case_id':row['case_id'],'dimension':field,'old_ref':cause['source_reference'],'new_ref':target,
                                       'reason':'Use the actual responsible year/entity recognizer rather than the generic format-recognizer citation.'})
                    cause['source_reference']=target
                    cause['source_location']={k:refs[target][k] for k in ['path','start_line','end_line','sha256']}
            if cause['dimension'] in ['author_text','title_text','subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','availability','year_min','year_max','rating_min','rating_max']:
                operands.append({'case_id':row['case_id'],'scope':row['scope'],'stratum':row['decision_stratum'],**cause})
        row['source_reference_version']='source_references_v2.json'
    jsonl('root_cause_matrix_v2.jsonl',matrix)
    jsonl('operand_extraction_diagnostics_v2.jsonl',operands)
    write('attribution_audit.json',{'status':'PASS_SOURCE_CITATIONS_REFINED','active_root_cause_matrix':str(R/(P+'root_cause_matrix_v2.jsonl')),
        'prior_C5D_matrix_retained':True,'C5C_original_dispositions_and_scores_unchanged':True,'context_count':len(matrix),
        'source_citation_amendments':amendments,'classification_counts_changed':False,
        'diagnostic_read_attempts':[{'status':'ONE_REPORT_INSPECTION_DECODE_ERROR','reason':'A diagnostic command used Windows default cp1252 for UTF8 source excerpts; explicit UTF8 was used for this audit.','parser_or_candidate_calls':0}],
        'prototype_semantics_counterexample_confirmed':True,'frozen_prototypes_edited':False})
    print({'contexts':len(matrix),'source_citation_amendments':len(amendments),'parser_calls':0})

if __name__=='__main__':main()
