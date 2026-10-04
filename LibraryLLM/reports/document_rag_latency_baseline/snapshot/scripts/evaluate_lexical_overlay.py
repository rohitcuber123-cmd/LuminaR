"""Isolated boundedness benchmark; never writes the published lexical base."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from search.lexical_build import build_snapshot
from search.lexical_delta import (DELTA_FILENAME,LexicalOverlayStore,initialize_delta)


class EmptyQueue:
    def latest(self): return 0


def run():
    results=[]
    plans=None
    with tempfile.TemporaryDirectory(prefix='luminar-overlay-') as temporary:
        for total in (2000,10000,50000):
            root=Path(temporary)/str(total)
            root.mkdir()
            docs=({'work_id':f'W{i:06d}','title':'Popular Title',
                   'authors':['Popular Author']} for i in range(total))
            manifest=build_snapshot(docs,root,source_db='luminar_library',limit=total)
            initialize_delta(root,manifest,0,EmptyQueue())
            delta=sqlite3.connect(root/DELTA_FILENAME)
            try:
                for percent in (0,50,90,99,100):
                    suppressed=total*percent//100
                    with delta:
                        delta.execute('DELETE FROM overrides')
                        delta.executemany('INSERT INTO overrides(work_id,deleted,last_event_seq) '
                                          'VALUES(?,1,1)',
                                          ((f'W{i:06d}',) for i in range(suppressed)))
                    reader=LexicalOverlayStore(root)
                    if not reader.health()['lexical_available']:
                        raise RuntimeError(reader.health())
                    try:
                        if plans is None:
                            queries=[('SELECT work_id FROM lexical_values WHERE value_type=? '
                                      'AND normalized_value=? ORDER BY work_id LIMIT ?',
                                      ('TITLE','popular title',128)),
                                     ('SELECT work_id FROM lexical_delta.lexical_values '
                                      'WHERE value_type=? AND normalized_value=? '
                                      'ORDER BY work_id LIMIT ?',('TITLE','popular title',50)),
                                     ('SELECT work_id FROM lexical_delta.overrides '
                                      'WHERE work_id IN (?,?)',('W000000','W000001'))]
                            plans=[' '.join(row[3] for row in reader.db.execute(
                                'EXPLAIN QUERY PLAN '+sql,args)) for sql,args in queries]
                        vm=[0]
                        reader.db.set_progress_handler(lambda: vm.__setitem__(0,vm[0]+100) or 0,100)
                        start=time.perf_counter()
                        ids=reader.work_ids_for_value('TITLE','popular title')
                        expansion_ms=(time.perf_counter()-start)*1000
                        expansion=dict(reader.last_read_budget)
                        start=time.perf_counter()
                        with reader._read_transaction():
                            eligible=reader._candidate_eligible('TITLE','popular title')
                        eligibility_ms=(time.perf_counter()-start)*1000
                        eligibility=dict(reader.last_read_budget)
                        start=time.perf_counter()
                        fuzzy=reader.fuzzy('TITLE','populr title')
                        fuzzy_ms=(time.perf_counter()-start)*1000
                        reader.db.set_progress_handler(None,0)
                        results.append({'base_ids':total,'overridden_percent':percent,
                                        'returned_work_ids':len(ids),'eligible':eligible,
                                        'expansion_budget':expansion,
                                        'eligibility_budget':eligibility,
                                        'fuzzy_budget':fuzzy['overlay_budget'],
                                        'fuzzy_reason':fuzzy['reason'],
                                        'expansion_ms':round(expansion_ms,3),
                                        'eligibility_ms':round(eligibility_ms,3),
                                        'fuzzy_ms':round(fuzzy_ms,3),
                                        'vm_steps_rounded_100':vm[0]})
                    finally:
                        reader.close()
            finally:
                delta.close()
    return {'plans':plans,'cases':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=run()
    encoded=json.dumps(report,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded+'\n',encoding='utf-8')
    print(encoded)
