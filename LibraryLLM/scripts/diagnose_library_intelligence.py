"""Local read-only tenant diagnostics; requires a separately provisioned Mongo read credential."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.services.library_operator_access import DiagnosticError,connect_operator
from backend.services.library_intelligence_diagnostics import inspect


class SafeParser(argparse.ArgumentParser):
    def error(self,message):
        raise DiagnosticError('INVALID_ARGUMENTS')


def readable(report):
    lines=['LuminaR tenant intelligence — read-only observation',
           'Library: '+report['library_id'],'Consistency: '+report['consistency'],
           'Worker health: '+report['worker']['classification'],'Process liveness: UNKNOWN',
           report['worker']['reason'],'Progress recency: UNKNOWN (no separate durable progress timestamp)',
           f"Database queue: {report['queue']['queued_total']} queued, {report['queue']['executing_total']} executing observations",
           'Queue ETA: NOT_AVAILABLE','Head of line: '+report['queue']['head_of_line'],
           'Job page (state / stage / actual progress counters):']
    for job in report['jobs']:
        p=job['progress']
        lines.append(f"  {job['job_id']}  {job['target']}  {job['state']} / {job['stage']}  {p['current']}/{p['total']}  heartbeat={job['heartbeat_evidence']} recovery={job['recovery_required']}")
    for target in report['targets']:
        lines.append(f"{target['target']}: published={target['published_generation_id']} previous={target['previous_generation_id']} integrity={target['published_checksum_integrity']}")
    lines+=['Artifacts: '+str(report['artifacts']['observed_generation_count'])+' observed; bounded coverage, no deletion',
            'Known-file bytes: '+str(report['artifacts']['observed_known_file_bytes'])]
    for artifact in report['artifacts']['generations']:
        lines.append(f"  {artifact['generation_id']} {artifact['target']} temporary={artifact['temporary']} present={artifact['directory_present']} {artifact['reconciliation']} manifest={artifact['manifest']} checksums={artifact['checksums']}")
    lines+=[
            'Worker CPU / memory / GPU: NOT_AVAILABLE','No action, retry, rebuild, recovery, cancellation or publication is available.']
    return '\n'.join(lines)


def main(argv=None):
    reader=None
    try:
        parser=SafeParser(description=__doc__)
        parser.add_argument('--library-id',required=True)
        parser.add_argument('--job-id')
        parser.add_argument('--database',default='luminar_library')
        parser.add_argument('--uri-env',default='LUMINAR_OPERATOR_MONGO_URI',help='Name of an existing secret environment variable; never a URI argument.')
        parser.add_argument('--state',action='append')
        parser.add_argument('--limit',type=int,default=20)
        parser.add_argument('--cursor')
        parser.add_argument('--artifact-root',type=Path)
        parser.add_argument('--artifact-limit',type=int,default=20)
        parser.add_argument('--verify-checksums',action='store_true')
        parser.add_argument('--checksum-budget-mib',type=int,default=16)
        parser.add_argument('--timeout-seconds',type=int,default=10)
        parser.add_argument('--format',choices=['json','text'],default='text')
        args=parser.parse_args(argv)
        reader=connect_operator(os.environ.get(args.uri_env),args.database,seconds=args.timeout_seconds)
        report=inspect(reader,args.library_id,states=args.state,limit=args.limit,cursor=args.cursor,job_id=args.job_id,
                       artifact_root=args.artifact_root,artifact_limit=args.artifact_limit,verify_checksums=args.verify_checksums,
                       checksum_budget=args.checksum_budget_mib*1024*1024)
        print(json.dumps(report,indent=2,allow_nan=False) if args.format=='json' else readable(report))
        return 0
    except DiagnosticError as error:
        print(json.dumps({'error':error.code,'read_only':True}),file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({'error':'DIAGNOSTIC_READ_UNAVAILABLE','read_only':True}),file=sys.stderr)
        return 3
    finally:
        if reader:
            try:reader.close()
            except Exception:pass


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf8')
    raise SystemExit(main())
