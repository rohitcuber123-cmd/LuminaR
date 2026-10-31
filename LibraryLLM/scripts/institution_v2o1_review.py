"""Source/byte review and proposed diffs only; never writes protected targets."""
import ast,difflib,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
    baseline=json.loads((R/'institution_v2j_baseline.json').read_text())
    page=ROOT/'frontend/src/pages/LibraryIntelligence.tsx'
    accepted=ROOT/'.scratch/institution-v2o/before/frontend/src/pages/LibraryIntelligence.tsx'
    assert sha(accepted.read_bytes())==baseline['source_sha256'][page.relative_to(ROOT).as_posix()]
    (R/'institution_v2o1_j_page_review.diff').write_text(''.join(difflib.unified_diff(accepted.read_text().splitlines(True),page.read_text().splitlines(True),fromfile='accepted-2J/LibraryIntelligence.tsx',tofile='accepted-2O/LibraryIntelligence.tsx')))
    rows=json.loads((R/'assistant_backend_baseline/hashes.json').read_text(encoding='utf-8-sig'))
    result={'J':{'expected':sha(accepted.read_bytes()),'actual':sha(page.read_bytes()),'recovered_J_page_matches_original_frozen_hash':True},'RAG':[]}
    for row in rows:
        path=Path(row['Path']);payload=path.read_bytes()
        result['RAG'].append({'path':str(path),'expected':row['Hash'],'actual':sha(payload).upper(),'asserted_by_frozen_test':path.name!='api.py','matches':sha(payload).upper()==row['Hash']})
    current=(ROOT/'rag/qa.py').read_bytes();git=subprocess.check_output(['git','show','HEAD:LibraryLLM/rag/qa.py'],cwd=ROOT)
    result['qa_git_equivalence']={'current_bytes':len(current),'git_bytes':len(git),'raw_current':sha(current),'git_blob':sha(git),
        'LF_normalized_current_matches_git_blob':current.replace(b'\r\n',b'\n')==git,
        'AST_equal':ast.dump(ast.parse(current.decode('utf-8-sig')))==ast.dump(ast.parse(git.decode('utf-8-sig'))),
        'CRLF_count':current.count(b'\r\n'),'LF_count':current.count(b'\n')}
    # Reconstruct a REVIEW artifact by reversing only the committed grounding
    # additions, preserving original byte line endings. Never copy it over qa.py.
    prefixes=[b'from rag.book_assets import valid_work_id',b'from rag.document_grounding import select_definition_evidence, definition_category',
        b'        is_document = bool(document_id and not valid_work_id(document_id))',b'        if is_document:',
        b'            results = select_definition_evidence(question, results, document_id, max_chunks)',
        b'            q_category = definition_category(question, used_items, document_id) or q_category']
    projected=b''.join(line for line in current.splitlines(keepends=True) if line.rstrip(b'\r\n') not in prefixes)
    original=b'        for item in ([] if is_document and verdict == "NOT_SUPPORTED" else used_items):'
    assert original in projected
    candidates=[]
    for ending in [b'\n',b'\r\n']:
        parts=projected.splitlines(keepends=True)
        candidate=b''.join(b'        for item in used_items:'+ending if line.rstrip(b'\r\n')==original else line for line in parts)
        digest=sha(candidate).upper();expected=next(r['Hash'] for r in rows if Path(r['Path']).name=='qa.py')
        candidates.append({'loop_line_ending':repr(ending),'sha256':digest,'matches_frozen_expected':digest==expected})
        if digest==expected:
            (R/'institution_v2o1_recovered_frozen_qa.txt').write_bytes(candidate)
            result['recovered_exact_frozen_qa']=True
    result['reverse_grounding_review_candidates']=candidates
    commits=subprocess.check_output(['git','log','--format=%H|%aI|%s','--','rag/qa.py'],cwd=ROOT,text=True).splitlines()
    result['qa_history']=commits
    for label,args in [('qa_committed',['git','diff','c449f54..HEAD','--','rag/qa.py']),('qa_worktree',['git','diff','--','rag/qa.py'])]:
        (R/f'institution_v2o1_{label}.diff').write_text(subprocess.check_output(args,cwd=ROOT,text=True))
    (R/'institution_v2o1_source_review.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'J_baseline_recovered':True,'qa_matches_committed_after_newline_normalization':result['qa_git_equivalence']['LF_normalized_current_matches_git_blob'],'exact_old_qa_recovered':result.get('recovered_exact_frozen_qa',False)}))


if __name__=='__main__':main()
