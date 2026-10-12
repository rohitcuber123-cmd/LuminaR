"""Read-only source/state/artifact inventory, captured before convergence edits."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
BASELINE = REPORTS / 'full_product_convergence_baseline.json'

def write(name, value):
    (REPORTS / name).write_text(value if isinstance(value,str) else json.dumps(value,indent=2,default=str),encoding='utf8')

def baseline():
    if BASELINE.exists(): return
    paths=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    source={}
    for name in paths:
        name=name.replace('\\','/'); p=ROOT/name
        if not name.startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.backup'} and p.stat().st_size<32*1024*1024:
            source[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    artifacts={}
    for directory in ['datasets','search','knowledge_graph','assistant/models']:
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and p.suffix in {'.index','.faiss','.hnsw','.bin','.npz','.npy','.duckdb','.safetensors','.pkl'}:
                s=p.stat();artifacts[p.relative_to(ROOT).as_posix()]={'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
    load_dotenv(ROOT/'.env')
    with MongoClient(os.getenv('MONGO_URI'),serverSelectionTimeoutMS=5000) as client:
        db=client['luminar_library']
        counts={n:db[n].estimated_document_count() if n=='books' else db[n].count_documents({}) for n in db.list_collection_names()}
        test={'library_id':'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'}
        test_records=list(db.institution_library_books.find(test,{'_id':0}).sort('library_book_id',1))
        test_holdings=list(db.institution_holdings.find(test,{'_id':0}).sort('library_book_id',1))
    prior={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in REPORTS.rglob('*') if p.is_file() and not p.name.startswith('full_product_')}
    write(BASELINE.name,{'captured_at':datetime.now(timezone.utc).isoformat(),'source_sha256':source,'prior_reports_sha256':prior,'production_counts':counts,'test_records':test_records,'test_holdings':test_holdings,'artifact_metadata':artifacts,'artifact_limits':'Size and mtime; no claim of hashing multi-GB artifacts.','authority':'Existing scoped LibraryMembership and PlatformRoleAssignment; no grants or migrations.'})
    print(f'Baseline: {len(source)} source files, {len(artifacts)} artifacts, {counts.get("books")} global books, {len(test_records)} TEST records.',flush=True)

def backend_inventory():
    modules=[];routes=[]
    for folder in ['backend','assistant','search','recommendation','rag']:
        for p in sorted((ROOT/folder).rglob('*.py')):
            if '__pycache__' in p.parts: continue
            text=p.read_text(encoding='utf-8-sig')
            try: tree=ast.parse(text)
            except SyntaxError: continue
            prefix={}
            imports=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func).endswith('APIRouter'):
                    for k in n.value.keywords:
                        if k.arg=='prefix' and isinstance(k.value,ast.Constant):
                            for t in n.targets: prefix[ast.unparse(t)]=k.value.value
                if isinstance(n,ast.ImportFrom): imports.append({'module':n.module,'names':[a.name for a in n.names]})
            functions=[]
            for n in ast.walk(tree):
                if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
                functions.append({'name':n.name,'line':n.lineno})
                for d in n.decorator_list:
                    if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in {'get','post','put','patch','delete','options','head'} and d.args and isinstance(d.args[0],ast.Constant):
                        deps=[ast.unparse(x.args[0]) for x in ast.walk(n) if isinstance(x,ast.Call) and ast.unparse(x.func)=='Depends' and x.args]
                        calls=sorted({ast.unparse(x.func) for x in ast.walk(n) if isinstance(x,ast.Call)})
                        routes.append({'method':d.func.attr.upper(),'path':prefix.get(ast.unparse(d.func.value),'')+str(d.args[0].value),'function':n.name,'file':p.relative_to(ROOT).as_posix(),'line':n.lineno,'dependencies':deps,'calls':calls})
            modules.append({'file':p.relative_to(ROOT).as_posix(),'lines':len(text.splitlines()),'imports':imports,'functions':functions})
    write('full_product_backend_discovery.json',{'routes':routes,'modules':modules})
    return routes,modules

def table(title,columns,rows):
    return f'# {title}\n\n'+'| '+' | '.join(columns)+' |\n| '+' | '.join(['---']*len(columns))+' |\n'+''.join('| '+' | '.join(str(v).replace('|',' / ').replace('\n',' ') for v in row)+' |\n' for row in rows)

def route_kind(r):
    p=r['route']
    if p in {'/staff/login','/staff/setup','/account/setup','/login','/signup','/verify-otp'}:return 'ACCOUNT','auth / setup APIs','public login or authenticated setup token','COMPATIBILITY' if 'Navigate' in r['element'] else 'CANONICAL'
    if p.startswith('/book/') and p.endswith('/read'):return 'ACCOUNT','protected digital reader API','authenticated session + existing digital entitlement','CANONICAL'
    if p.startswith('/staff/libraries'):return 'STAFF','tenant APIs','LibraryMembership ADMIN/LIBRARIAN','CANONICAL'
    if p.startswith('/platform'):return 'PLATFORM','platform APIs','PlatformRoleAssignment','CANONICAL'
    if p.startswith('/libraries/:'):return 'PATRON','library catalogue/lending/reservations/fees','LibraryMembership GENERAL_USER','CANONICAL'
    if any(s in r['element'] for s in ['Navigate','Redirect','AccountLanding']):return 'ACCOUNT','redirect / membership list','authenticated session + destination guard','COMPATIBILITY'
    if p.startswith(('/account','/reading-list','/invitations','/libraries')):return 'ACCOUNT','personal / institution APIs','authenticated session','CANONICAL'
    if p.startswith(('/login','/signup','/verify','/setup','/staff-login')):return 'ACCOUNT','auth APIs','public or setup token','CANONICAL'
    return 'GLOBAL','global catalogue / search / RAG / events / KG','public reads or authenticated feature guard','CANONICAL'

def frontend_decision(name):
    if any(x in name for x in ['LibraryCatalogueBook','api/core','institutions.ts']): return 'KEEP: typed adapter to shared composition/transport; no independent writer or visual surface'
    if any(x in name for x in ['BookCard','BookCover','BookDetailView','CatalogueSurface','GlobalCatalogue','ProductPagination','BookPersonalActions','DiscoveryBookFrame']): return 'CANONICAL SHARED: mature product composition, explicit data/capability inputs'
    if any(x in name for x in ['LibraryInventory','LibraryCirculation','LibraryReservationsFees','LibraryActivity','InstitutionPanel','Platform','WorkspaceRoute','LibraryShells']): return 'KEEP CONTEXT-SPECIFIC: canonical LibraryMembership / PlatformRoleAssignment guard; distinct operational purpose'
    if any(x in name for x in ['CatalogPage','SearchPage','BookDetailPage','LibraryCatalogue.tsx']): return 'KEEP: route data adapter; shared book/catalogue composition'
    if any(x in name for x in ['readNow.ts','ProfilePage','ManagementRoutes']): return 'COMPATIBILITY: historic read-only/redirect or unused legacy helper; no canonical physical writer'
    if any(x in name for x in ['productContext','libraryWorkspace','useProductContext','useInstitutionStore']): return 'KEEP: explicit URL context / membership projections; remembered state cannot override canonical URL'
    if '/store/' in name: return 'KEEP: one store per distinct concept; token/owner guards retained; no parallel selection/saved/membership store'
    if '/lib/' in name or '/api/' in name or '/hooks/' in name: return 'KEEP: distinct typed contract/helper over common request transport; source callers inventoried'
    if any(x in name for x in ['knowledge','Knowledge','LLM','MindMap','Quiz','Cloze','RAG','DeviceDocuments','Document','Reader','SourceLink']): return 'KEEP ACCOUNT-SHARED: private knowledge/digital entitlement, frozen contract; return context is presentation metadata'
    if any(x in name for x in ['Event','Notification']): return 'KEEP PLATFORM/PERSONAL-SHARED: existing global event/account notification service; no tenancy added'
    if 'AuthLayout' in name: return 'KEEP: decorative login covers, not inventory or availability data'
    return 'KEEP SHARED: distinct composed product/auth/discovery/control purpose; callers and frozen tests retained'

def backend_decision(r):
    p=r['path']; name=r['file']
    if '/libraries/' in p: return 'TENANT_CANONICAL: guarded membership and tenant-scoped service; no global role grant'
    if any(x in name for x in ['/issues.py','/reservations.py','/fines.py','/library_inventory.py']): return 'COMPATIBILITY: historic reads; retired physical writes return 410 (digital entitlement reads retained)'
    if '/platform' in p: return 'PLATFORM_CANONICAL: explicit assignment; no implicit tenant membership'
    if '/books' in p and r['method'] in {'POST','PUT','PATCH','DELETE'}: return 'PLATFORM_GLOBAL_METADATA: explicit assignment; rejects physical stock/shelf mutation'
    if any(x in p for x in ['reading-list','/auth','/me/','/documents','/knowledge','/quiz','/cloze','/loans']): return 'PERSONAL_SHARED: owner/auth/entitlement contract; separate from tenant operations'
    return 'KEEP DISTINCT GLOBAL/PERSONAL: metadata/search/recommendation/Assistant/KG/event/read capability contract; see duplicate-review rationale'

def main():
    baseline()
    subprocess.run(['node',str(ROOT/'scripts/full_product_inventory.cjs')],cwd=ROOT,check=True)
    front=json.loads((REPORTS/'full_product_frontend_discovery.json').read_text())
    backend,modules=backend_inventory()
    rows=[]
    for r in front['routes']:
        kind,data,authority,status=route_kind(r)
        rows.append([r['route']+(' (index)' if r['index'] else ''),r['element'],kind,data,authority,status,'Home / catalogue / detail counterparts' if kind=='PATRON' else 'see feature parity matrix',f"{r['file']}:{r['line']}"])
    write('full_route_inventory.md',table('Full frontend route inventory',['Route','Component / purpose','Context','Data','Authority','Classification','Overlap','Source'],rows))
    components=[m for m in front['modules'] if '/components/' in m['file'] or '/pages/' in m['file']]
    write('full_frontend_component_inventory.md',table('Full frontend page and component inventory',['Module','Exported implementations','Local compositions','Hooks / state','Children','Decision'],[[m['file'],', '.join(m['exports']),', '.join(m['functions']),', '.join(m['hooks']),', '.join(n for n in m['jsx'] if n[:1].isupper()),frontend_decision(m['file'])] for m in components]))
    write('full_state_store_inventory.md',table('Full state / API / helper inventory',['Module','Exports','Dependencies','Uses','Purpose / decision'],[[m['file'],', '.join(m['exports']),', '.join(m['imports']),', '.join(m['hooks']),frontend_decision(m['file'])] for m in front['modules'] if any(s in m['file'] for s in ['/store/','/hooks/','/lib/','/api/'])]))
    write('full_backend_feature_inventory.md',table('Full backend HTTP feature inventory',['Method','Path','Implementation','Authority dependencies','Calls','Classification'],[[r['method'],r['path'],f"{r['file']}:{r['line']} {r['function']}",', '.join(r['dependencies']),', '.join(r['calls']),backend_decision(r)] for r in backend])+ '\n\n## Services and models\n\n'+table('Source modules',['Module','Functions / methods','Imports'],[[m['file'],', '.join(f['name'] for f in m['functions']),', '.join(i['module'] or '' for i in m['imports'])] for m in modules]))
    css=[]
    for p in sorted((ROOT/'frontend/src').rglob('*.css')):
        source=p.read_text(encoding='utf8');selectors=re.findall(r'([^{}]+)\{',source)
        css.append([p.relative_to(ROOT).as_posix(),len(source.splitlines()),len(selectors),' / '.join(s.strip() for s in selectors[:8]),'CANONICAL SHARED BOOK SURFACES' if p.name=='product.css' else 'KEEP: distinct workspace/event/document/cache/diagram or base tokens; no parallel catalogue/detail rules'])
    write('full_css_inventory.md',table('Full stylesheet inventory',['Stylesheet','Lines','Rule blocks','Representative selectors','Decision'],css))
    write('full_product_inventory_counts.json',{'route_declarations':len(front['routes']),'frontend_modules':len(front['modules']),'frontend_page_component_modules':len(components),'backend_http_paths':len(backend),'backend_modules':len(modules),'stylesheets':len(css)})
    print(f'Inventories: {len(front["routes"])} frontend routes, {len(components)} page/component modules, {len(backend)} backend HTTP paths, {len(modules)} Python modules, {len(css)} stylesheets.',flush=True)

if __name__=='__main__':main()
