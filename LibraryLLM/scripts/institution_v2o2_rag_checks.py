"""All focused production RAG/grounding/isolation tests, no research training."""
from pathlib import Path
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]


def main():
    groups={'grounding_security':['tests/test_private_document_cache.py','tests/test_private_preparation_status.py',
        'tests/test_document_rag_latency.py','tests/test_rag_query_types.py','tests/test_rag_hard_negatives.py',
        'tests/test_document_knowledge.py','tests/test_knowledge_artifacts.py','tests/test_knowledge_tools_v2_1.py',
        'tests/test_urgent_document_rag.py','tests/test_rag_attention.py','tests/test_rag_decoding.py',
        'tests/institution_v2o1/test_rag_evidence_validation.py','tests/institution_v2o2/test_grounding_boundary.py'],
        'library_asset_security':['tests/institution_v2f'],
        'lexical_fallback':['tests/test_lexical_api_fallback.py','tests/institution_v2o/test_facet_fallback.py']}
    rows=[]
    for name,targets in groups.items():
        xml=ROOT/f'reports/institution_v2o2_{name}.xml';start=time.perf_counter()
        with xml.with_suffix('.log').open('w',encoding='utf8') as out:
            p=subprocess.run([sys.executable,'-m','pytest',*targets,'-q','--junitxml='+str(xml)],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,timeout=900)
        cases=list(ET.parse(xml).iter('testcase'));failed=sum(any(n.tag in {'failure','error'} for n in c) for c in cases);skip=sum(any(n.tag=='skipped' for n in c) for c in cases)
        rows.append({'group':name,'exit':p.returncode,'passed':len(cases)-failed-skip,'failed':failed,'skipped':skip,'seconds':time.perf_counter()-start,'targets':targets,'xml':xml.name})
        (ROOT/'reports/institution_v2o2_rag_grounding_tests.json').write_text(json.dumps({'groups':rows},indent=2));print(json.dumps(rows[-1]),flush=True)
    return any(row['exit'] for row in rows)


if __name__=='__main__':raise SystemExit(main())
