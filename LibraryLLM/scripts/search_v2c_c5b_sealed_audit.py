"""Invoke the unchanged established sealed audit with a C5B output namespace.

Only the evidence-tool PREFIX parameter changes in memory. All structural,
canonical, scope and sealed-access rules remain the hash-verified C5A interface.
Never executes parser/evaluator/policy code or exposes sealed row contents.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';P='search_v2c_c5b_'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def established():
    source=ROOT/'scripts/search_v2c_c5a_sealed_audit.py'
    baseline=json.loads((R/(P+'baseline.json')).read_text())
    expected=baseline['protected_files']['scripts\\search_v2c_c5a_sealed_audit.py']
    assert sha(source)==expected,'ESTABLISHED_AUDITOR_CHANGED'
    spec=importlib.util.spec_from_file_location('c5b_established_sealed_interface',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,source,expected

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();module,source,expected=established()
    inp=module.local_path(args.input);out=module.local_path(args.output)
    assert inp.parent==R and inp.name.startswith(P) and inp.suffix=='.jsonl'
    assert out.parent==R and out.name.startswith(P) and out.suffix=='.json'
    old_log=R/'search_v2c_c5a_sealed_access_audit.json';old_log_hash=sha(old_log)
    module.PREFIX=P
    result=module.audit(inp,out)
    assert sha(source)==expected and sha(old_log)==old_log_hash,'C5A_INTERFACE_OR_LOG_CHANGED'
    # The frozen tool's literal metadata key names its old namespace. Translate
    # only that trace key in the NEW log; structural results/rules stay intact.
    trace_path=R/(P+'sealed_access_audit.json');trace=json.loads(trace_path.read_text())
    for run in trace['runs']:
        flag=run.pop('only_new_c5a_reports_written',run.get('only_current_namespace_reports_written',True))
        run['only_current_namespace_reports_written']=flag
        run['write_namespace']=P;run['C5A_reports_written']=False
    trace['namespace_metadata_translation']='Frozen C5A trace flag is parameterized by the runtime PREFIX; its key is renamed in C5B output to avoid implying any C5A write.'
    trace_path.write_text(json.dumps(trace,sort_keys=True,indent=2)+'\n')
    provenance={'version':'C5B-established-audit-namespace-adapter-v1','established_source':str(source.relative_to(ROOT)),
        'established_source_sha256':expected,'adapter_sha256':sha(Path(__file__)),'only_parameter_change':{'PREFIX':{'from':'search_v2c_c5a_','to':P}},
        'algorithms_changed':False,'trace_metadata_key_translation_only':True,'C5A_source_changed':False,'C5A_audit_log_changed':False,'input':str(inp.relative_to(ROOT)),'input_sha256':sha(inp),
        'output':str(out.relative_to(ROOT)),'output_sha256':sha(out),'sealed_text_or_labels_exposed':False,'parser_calls':0,'policy_calls':0}
    (R/(P+'sealed_interface_provenance.json')).write_text(json.dumps(provenance,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
