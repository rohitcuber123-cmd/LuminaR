"""Immutable Part 2G baseline and builder reuse audit; no global build invocation."""
from pathlib import Path
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from scripts.institution_v2f_baseline import digest
from scripts.institution_v2f_preservation import personal_snapshot
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def capture():
    target=ROOT/'reports/institution_v2g_baseline.json'
    if target.exists():return json.loads(target.read_text(encoding='utf8'))
    assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
    frozen=json.loads((ROOT/'reports/institution_v2f_baseline.json').read_text())
    sources={}
    for folder in ['backend','frontend/src','search','knowledge_graph','assistant','rag','recommendation']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ['.py','.tsx','.ts','.css','.json'] and '__pycache__' not in p.parts:
                sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    rows={n:{'count':db[n].count_documents({'library_id':TEST}),'sha256':digest(list(db[n].find({'library_id':TEST},{'_id':0})))} for n in ['institution_library_books','institution_holdings','institution_library_assets']}
    artifacts={n:{'bytes':(ROOT/n).stat().st_size,'mtime_ns':(ROOT/n).stat().st_mtime_ns} for n in frozen['artifact_metadata']}
    result={'captured_at':datetime.now(timezone.utc).isoformat(),'TEST':rows,'global_book_count':db.books.estimated_document_count(),'source_sha256':sources,'global_artifact_metadata':artifacts,'personal_logical':personal_snapshot(ROOT/'rag/private_documents/registry.sqlite'),'authority':'No account grants; explicit active LibraryMembership ADMIN required for builds.','global_build_invoked':False}
    target.write_text(json.dumps(result,indent=2),encoding='utf8')
    audits={
      'search_builder': [('search/catalogue.py','REUSE_DIRECTLY','Deterministic semantic text and content hashes; descriptive metadata only.'),('search/index_manager.py','REUSE_WITH_TENANT_ADAPTER','Reuse checksum, durable serialization and normalized HNSW concepts; independent UUID generations and tenant-scale parameters.'),('search/embedding_cache.py','REUSE_WITH_TENANT_ADAPTER','Global cache keyed by work_id cannot be shared blindly. Tenant model/schema/text hash cache stays in tenant root.'),('search/luminar_search.py','GLOBAL_ONLY','Frozen resident model/reranker reused as injected primitives; no global ranking edits.'),('search/api.py','REUSE_WITH_TENANT_ADAPTER','Mount independent tenant routes/worker on existing resident Search process.'),('search/maintenance.py','UNSAFE_FOR_TENANT','Global paths/queues/build control cannot be invoked for library jobs.')],
      'kg_builder':[('knowledge_graph/core.py','REUSE_DIRECTLY','Canonical term and feature identity helpers, typed metadata relationships.'),('knowledge_graph/relations.py','REUSE_DIRECTLY','Author/subject relation labels; no LLM-generated edges.'),('scripts/build_catalogue_graph.py','REUSE_WITH_TENANT_ADAPTER','Pure row/path builder is deterministic but global main/default paths and 128MiB tuning are inappropriate for tenant use.'),('knowledge_graph/data/catalogue.sqlite','GLOBAL_ONLY','Frozen read-only global artifact. Never rebuild or use as a tenant-labelled graph.')],
      'artifact':[('search/index_manager.py','REUSE_WITH_TENANT_ADAPTER','Private generations, fsync, checksum validation and atomic pointer principles.'),('backend/services/library_asset_service.py','REUSE_WITH_TENANT_ADAPTER','Canonical UUID path containment and symlink rejection; asset corpus remains distinct.'),('rag/services/library_asset_pipeline.py','GLOBAL_ONLY','Document chunks/runtime FAISS are not catalogue sources.'),('backend/services/institution_repository.py','REUSE_DIRECTLY','Canonical tenant barrier and durable mutation context.')],
      'job_reuse':[('backend/services/library_asset_service.py','REUSE_WITH_TENANT_ADAPTER','Durable queue/leases/worker fences/publication safety pattern; independent build targets and collections required.'),('search/sync_queue.py','GLOBAL_ONLY','Existing global immutable-base/delta queue remains frozen.'),('backend/services/library_lending_journal.py','GLOBAL_ONLY','Unknown-outcome fail-closed precedent; no lending schema changes.'),('backend/services/library_inventory_access.py','REUSE_DIRECTLY','Fresh membership/lifecycle guards; platform role grants no tenant membership.')]
    }
    for name,entries in audits.items():
        title={'artifact':'artifact','job_reuse':'job_reuse','search_builder':'search_builder','kg_builder':'kg_builder'}[name]
        text='Part 2G audit completed before tenant implementation. Global builders were inspected, never executed.\n\n| Existing code | Classification | Decision |\n|---|---|---|\n'+''.join(f'| {p} | {kind} | {note} |\n' for p,kind,note in entries)
        (ROOT/f'reports/institution_v2g_{title}_audit.md').write_text(text,encoding='utf8')
    print(json.dumps({'baseline':'saved','TEST':rows['institution_library_books']['count'],'holdings':rows['institution_holdings']['count'],'global_count':result['global_book_count'],'frozen_artifacts':len(artifacts),'source_files':len(sources)}))
    return result
if __name__=='__main__':capture()
