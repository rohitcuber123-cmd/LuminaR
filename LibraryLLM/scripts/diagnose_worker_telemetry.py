"""Independent Mongo-read-authenticated, bounded local worker telemetry supplement."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.services.library_operator_access import connect_operator,DiagnosticError
from backend.services.library_worker_diagnostics import inspect_telemetry


class Parser(argparse.ArgumentParser):
    def error(self,message):raise DiagnosticError('INVALID_ARGUMENTS')


def main(argv=None):
    reader=None
    try:
        p=Parser(description=__doc__);p.add_argument('--library-id',required=True)
        p.add_argument('--database',default='luminar_library');p.add_argument('--format',choices=['json','text'],default='text')
        a=p.parse_args(argv)
        reader=connect_operator(os.environ.get('LUMINAR_OPERATOR_MONGO_URI'),a.database,seconds=5)
        r=inspect_telemetry(reader,a.library_id)
        if a.format=='json':print(json.dumps(r,sort_keys=True,allow_nan=False))
        else:
            print('\n'.join(['LuminaR worker telemetry — read-only observation',
                'Worker self-report: '+r['worker']['classification'],
                'Previous instance (historical): '+r['previous_worker']['classification'],
                'Idle (latest report): '+str(r['worker']['idle']),
                'Last pulse age seconds: '+str(r['worker']['pulse_age_seconds']),
                'Associated scoped job: '+json.dumps(r['associated_job']),
                'Process verification: NOT_AVAILABLE','Stalled: NOT_DETERMINED',r['worker']['evidence'],
                'Accepted progress observations: '+json.dumps(r['progress'],sort_keys=True)]))
        return 0
    except DiagnosticError as e:print(json.dumps({'error':e.code,'read_only':True}),file=sys.stderr);return 2
    except Exception:print(json.dumps({'error':'TELEMETRY_READ_UNAVAILABLE','read_only':True}),file=sys.stderr);return 3
    finally:
        if reader:reader.close()


if __name__=='__main__':raise SystemExit(main())
