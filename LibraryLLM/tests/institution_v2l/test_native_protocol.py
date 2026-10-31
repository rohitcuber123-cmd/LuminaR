"""Preserve the original J worker protocol without freezing an authorized observer seam."""
import ast,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_native_protocol_matches_original_j_baseline():
    original=(Path(__file__).parent/'fixtures/native_worker_before.txt').read_bytes()
    baseline=json.loads((ROOT/'reports/institution_v2j_baseline.json').read_text(encoding='utf8'))
    assert hashlib.sha256(original).hexdigest()==baseline['source_sha256']['search/library_intelligence.py']
    before=ast.parse(original.decode('utf8'));after=ast.parse((ROOT/'search/library_intelligence.py').read_text(encoding='utf8'))
    def method(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    events=[];forwarded=[]
    class Normalize(ast.NodeTransformer):
        def visit_Expr(self,node):
            call=node.value
            if (isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name)
                    and call.func.value.id=='self' and call.func.attr=='_observe'):
                events.append(call.args[0].value);return None
            return self.generic_visit(node)
        def visit_Call(self,node):
            if (isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
                    and node.func.value.id=='self' and node.func.attr=='_progress'):
                forwarded.append(True)
                node.func=ast.Attribute(value=ast.Name(id='store',ctx=ast.Load()),attr='progress',ctx=ast.Load())
            return self.generic_visit(node)
    transformed=Normalize().visit(method(after,'run_one'))
    assert events==['claimed','finished'] and len(forwarded)==3
    assert ast.dump(method(before,'run_one'),include_attributes=False)==ast.dump(transformed,include_attributes=False)
    assert ast.dump(method(before,'semantic'),include_attributes=False)==ast.dump(method(after,'semantic'),include_attributes=False)
    assert hashlib.sha256((ROOT/'backend/services/library_intelligence_store.py').read_bytes()).hexdigest()==baseline['source_sha256']['backend/services/library_intelligence_store.py']
