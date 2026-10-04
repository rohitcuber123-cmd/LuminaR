"""Measure isolated delta growth without changing Mongo or the published sidecar."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from search.lexical_build import build_snapshot
from search.lexical_delta import initialize_delta,LexicalDeltaWriter


class Queue:
    def __init__(self): self.events=[]
    def latest(self): return self.events[-1][0] if self.events else 0
    def pending(self,after): return [event for event in self.events if event[0]>after]
    def add(self,ids):
        self.events.append((self.latest()+1,'sync',json.dumps(ids)))


class Books:
    def __init__(self): self.docs={}
    def find_one(self,query,projection): return self.docs.get(query['work_id'])


def run():
    cases=[]
    with tempfile.TemporaryDirectory(prefix='luminar-delta-growth-') as temporary:
        for count in (10,100,1000):
            root=Path(temporary)/str(count)
            root.mkdir()
            base=build_snapshot([{'work_id':'BASE','title':'Base',
                                  'authors':['Base Author']}],root,
                                source_db='luminar_library')
            queue=Queue();books=Books()
            initialize_delta(root,base,0,queue)
            writer=LexicalDeltaWriter(root,books,queue)
            ids=[f'SYN{i:06d}' for i in range(count)]
            try:
                initial=writer.status()
                for wid in ids:
                    books.docs[wid]={'work_id':wid,'title':'Test Title '+wid,
                                     'authors':['Test Author '+wid]}
                queue.add(ids)
                if not writer.process_once(): raise RuntimeError('Synthetic create failed')
                created=writer.status()
                for wid in ids: books.docs[wid]['title']='Updated Title '+wid
                queue.add(ids)
                if not writer.process_once(): raise RuntimeError('Synthetic update failed')
                updated=writer.status()
                for wid in ids: del books.docs[wid]
                queue.add(ids)
                if not writer.process_once(): raise RuntimeError('Synthetic delete failed')
                deleted=writer.status()
                cases.append({'count':count,'initial':initial,'after_create':created,
                              'after_update':updated,'after_delete':deleted,
                              'create_bytes_per_override':round(
                                  (created['delta_size_bytes']-initial['delta_size_bytes'])/count,2)})
            finally:
                writer.close()
    return {'cases':cases}


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
