"""Read-only telemetry laboratory supplement; fixture namespace only."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.services.library_operator_access import DiagnosticError,connect_operator
from scratch.institution_v2k_telemetry.observer import inspect_telemetry
from scratch.institution_v2k_telemetry.telemetry import PREFIX


class Parser(argparse.ArgumentParser):
    def error(self,message):raise DiagnosticError('INVALID_ARGUMENTS')


def main():
    reader=None
    try:
        p=Parser(description=__doc__)
        p.add_argument('--database',required=True);p.add_argument('--library-id',required=True)
        p.add_argument('--format',choices=['json','text'],default='json')
        a=p.parse_args()
        if not a.database.startswith(PREFIX):raise DiagnosticError('PROTOTYPE_FIXTURE_ONLY')
        reader=connect_operator(os.environ.get('LUMINAR_OPERATOR_MONGO_URI'),a.database,seconds=3)
        result=inspect_telemetry(reader,a.library_id)
        print(json.dumps(result,sort_keys=True) if a.format=='json' else '\n'.join([
            'LuminaR 2K isolated prototype — read-only',
            'Worker self-report: '+result['worker']['classification'],
            'Process independently verified: NO',
            'Stalled: NOT_DETERMINED',
            result['worker']['evidence'],
            'Correlated progress: '+json.dumps(result['progress'],sort_keys=True)]))
        return 0
    except DiagnosticError as e:print(json.dumps({'error':e.code,'read_only':True}),file=sys.stderr);return 2
    except Exception:print(json.dumps({'error':'TELEMETRY_UNAVAILABLE','read_only':True}),file=sys.stderr);return 3
    finally:
        if reader:reader.close()


if __name__=='__main__':raise SystemExit(main())
