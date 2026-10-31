"""Whole first-party repository client/operation/import inventory without serializing URI values."""
import ast,hashlib,json,re,subprocess,sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OPS={'find','find_one','aggregate','count_documents','estimated_document_count','distinct','insert_one','insert_many','update_one','update_many',
    'replace_one','find_one_and_update','find_one_and_replace','find_one_and_delete','delete_one','delete_many','bulk_write','create_index','create_indexes',
    'list_indexes','index_information','drop_index','drop_indexes','list_collection_names','list_collections','create_collection','command',
    'start_session','start_transaction','with_transaction','watch','drop_database','drop_collection','rename'}


def function_at(tree,line):
    names=[(n.end_lineno-n.lineno,n.name) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.lineno<=line<=n.end_lineno]
    return min(names)[1] if names else '<module>'


def expression(node):
    # Do not emit any string/URI literal or source argument value.
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):return expression(node.value)+'.'+node.attr
    if isinstance(node,ast.Subscript):return expression(node.value)+'[collection]'
    if isinstance(node,ast.Call):return expression(node.func)+'(...)'
    return type(node).__name__


def main():
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!datasets','-g','*.py','-g','*.ps1','-g','*.toml','-g','*.env*'],cwd=ROOT,text=True).splitlines()
    clients=[];operations=[];config=[];imports={};unparsed=[];archives=0;activefiles=0;aliases={};trees={};calls=[]
    for name in names:
        path=ROOT/name;rel=path.relative_to(ROOT).as_posix()
        if any(x in path.relative_to(ROOT).parts for x in ['reports','.scratch','scratch']):archives+=1;continue
        if path.stat().st_size>4*1024*1024:unparsed.append({'path':rel,'reason':'size_limit'});continue
        text=path.read_text(encoding='utf8',errors='replace')
        # Environment files are values-sensitive; record key names/presence only.
        if path.name.startswith('.env'):
            for line in text.splitlines():
                m=re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=',line)
                if m:config.append({'path':rel,'line':None,'setting':m.group(1),'value_recorded':False})
            continue
        if path.suffix!='.py':
            for i,line in enumerate(text.splitlines(),1):
                for m in re.finditer(r'\b(?:MONGO[A-Z0-9_]*|MONGODB[A-Z0-9_]*|DATABASE_URL|LUMINAR_MONGO[A-Z0-9_]*)\b',line):config.append({'path':rel,'line':i,'setting':m.group(0),'value_recorded':False})
            continue
        try:tree=ast.parse(text)
        except SyntaxError:unparsed.append({'path':rel,'reason':'syntax_error'});continue
        activefiles+=1;trees[rel]=tree;module=rel[:-3].replace('/','.')
        imports[module]=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom) and n.module:
                imports[module].append({'module':n.module,'names':[v.name for v in n.names],'line':n.lineno})
                for a in n.names:aliases[(module,a.asname or a.name)]=n.module+'.'+a.name
            elif isinstance(n,ast.Import):
                imports[module]+=[{'module':a.name,'names':[],'line':n.lineno} for a in n.names]
                for a in n.names:aliases[(module,a.asname or a.name)]=a.name
            if isinstance(n,ast.Call):
                callee=expression(n.func);resolved=aliases.get((module,callee),callee)
                if callee.split('.')[-1] in ['MongoClient','AsyncIOMotorClient'] or resolved.endswith(('.MongoClient','.AsyncIOMotorClient')):
                    clients.append({'path':rel,'line':n.lineno,'function':function_at(tree,n.lineno),'constructor':resolved,
                        'scope':'runtime' if rel.split('/')[0] in ['backend','search','recommendation','rag','knowledge_graph'] and '/scripts/' not in rel else 'tests' if rel.startswith('tests/') else 'operator/script',
                        'argument_symbols':[expression(a) for a in n.args],'option_names':[k.arg for k in n.keywords],
                        'credential_values_recorded':False,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                if isinstance(n.func,ast.Attribute) and n.func.attr in OPS:operations.append({'path':rel,'line':n.lineno,'function':function_at(tree,n.lineno),'receiver':expression(n.func.value),'operation':n.func.attr,
                    'constant_collection':n.func.value.slice.value if isinstance(n.func.value,ast.Subscript) and isinstance(n.func.value.slice,ast.Constant) and isinstance(n.func.value.slice.value,str) else None})
                if (isinstance(n.func,ast.Attribute) and n.func.attr in ['getenv','get'] or isinstance(n.func,ast.Name) and n.func.id=='getenv') and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):
                    key=n.args[0].value
                    if any(s in key for s in ['MONGO','DATABASE_URL']):config.append({'path':rel,'line':n.lineno,'setting':key,'value_recorded':False})
                if isinstance(n.func,ast.Name):calls.append((rel,n.lineno,n.func.id))
    # Resolve Mongo collection aliases imported from the common module and
    # literal db attributes/subscripts/institution collection helpers.
    bindings={};base=trees.get('backend/database/mongodb.py')
    for n in ast.walk(base):
        if isinstance(n,ast.Assign) and isinstance(n.value,ast.Subscript) and isinstance(n.value.value,ast.Name) and n.value.value.id=='db' and isinstance(n.value.slice,ast.Constant):
            for t in n.targets:
                if isinstance(t,ast.Name):bindings['backend.database.mongodb.'+t.id]=n.value.slice.value
    constants={}
    for rel,tree in trees.items():
        module=rel[:-3].replace('/','.')
        for n in tree.body:
            if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):
                for target in n.targets:
                    if isinstance(target,ast.Name):constants[module+'.'+target.id]=n.value.value
    def resource(node,module,local):
        if isinstance(node,ast.Name):return local.get(node.id) or bindings.get(aliases.get((module,node.id),module+'.'+node.id))
        if isinstance(node,ast.Attribute):
            root=expression(node.value)
            if root in ['db','database','self.db','self.database','self.mongo_db']:return node.attr
            return local.get(expression(node))
        if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str):
            root=expression(node.value)
            if root in ['db','database','self.db','self.database','self.mongo_db']:return node.slice.value
        if isinstance(node,ast.Call) and node.args:
            arg=node.args[0]
            value=arg.value if isinstance(arg,ast.Constant) else constants.get(aliases.get((module,arg.id),module+'.'+arg.id)) if isinstance(arg,ast.Name) else None
            name=expression(node.func)
            if not isinstance(value,str):return None
            if name.split('.')[-1]=='collection' and any(s in module for s in ['backend.','search.library_intelligence']):return 'institution_'+value
        return None
    resolved=[]
    for rel,tree in trees.items():
        module=rel[:-3].replace('/','.');local={}
        for _ in range(3):
            for n in ast.walk(tree):
                if isinstance(n,ast.Assign):
                    v=resource(n.value,module,local)
                    if v:
                        for target in n.targets:local[expression(target)]=v
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in OPS:
                coll=resource(n.func.value,module,local)
                if coll:resolved.append({'path':rel,'line':n.lineno,'function':function_at(tree,n.lineno),'collection':coll,'operation':n.func.attr})
    result={'scan_policy':'Whole first-party current repository via rg; .git/venv/node_modules/datasets excluded. Historical reports/scratch are classified as archived copies, not active clients. No URI/secret argument values serialized.',
        'python_files_parsed':activefiles,'historical_snapshot_files_excluded':archives,'unparsed':unparsed,'clients':clients,'operations':operations,'resolved_collection_operations':resolved,
        'configuration_settings':config,'import_graph':imports,'collection_export_aliases':bindings,
        'limits':['Static import/call graph is conservative, not a proof that every imported function executes in every process.','Dynamic collection helpers/aggregation lookups/exec-generated harnesses require source review and runtime command evidence.','A method named find may belong to a non-Mongo object unless its resource resolves.']}
    out=ROOT/'reports/institution_v2n_client_inventory.json';out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'python_files':activefiles,'client_sites':len(clients),'resolved_operations':len(resolved),'unparsed':len(unparsed)}))


if __name__=='__main__':main()
