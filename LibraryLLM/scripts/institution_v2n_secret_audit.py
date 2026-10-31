"""Record secret locations/key names and possible URI leaks without values."""
import json
import re
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    source = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv', '-g', '!node_modules', '-g', '!datasets', '-g', '*.env*'], cwd=ROOT, text=True).splitlines()
    keys = []
    for name in source:
        path = ROOT / name
        if any(p in {'.scratch', 'scratch', 'reports'} for p in path.parts): continue
        for number, line in enumerate(path.read_text(encoding='utf8', errors='replace').splitlines(), 1):
            match = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)', line)
            if match and any(part in match[1] for part in ['SECRET', 'PASSWORD', 'TOKEN', 'MONGO', 'DATABASE_URL', 'SMTP']):
                value = match[2].strip()
                keys.append({'path': path.relative_to(ROOT).as_posix(), 'line': number, 'key': match[1], 'nonempty': bool(value),
                             'mongodb_userinfo_present': bool(re.search(r'mongodb(?:\+srv)?://[^\s]+@', value)), 'value_recorded': False})
    findings = []
    candidates = [*ROOT.glob('reports/institution_v2n_*'), *ROOT.glob('.local/logs/*.log')]
    credential = re.compile(r'mongodb(?:\+srv)?://[^\s/@:\'\"]+:[^\s@\'\"]+@')
    for path in candidates:
        if path.suffix not in {'.md', '.json', '.log', '.xml'}: continue
        for number, line in enumerate(path.read_text(encoding='utf8', errors='replace').splitlines(), 1):
            for match in credential.finditer(line):
                # Frozen J test case identifiers contain this public static
                # invalid-host literal; preserve evidence, classify it accurately.
                literal = match.group(0)
                dummy = literal == 'mongodb://name:password@' and 'foreign.invalid' in line
                findings.append({'path': path.relative_to(ROOT).as_posix(), 'line': number,
                                 'kind': 'STATIC_NEGATIVE_TEST_LITERAL' if dummy else 'credential_URI_pattern_requires_review',
                                 'value_recorded': False})
    result = {'environment_key_locations': keys, 'credential_URI_pattern_findings': findings,
              'limits': 'Pattern scan is not proof that arbitrary tokens/passwords never appear in all logs/processes. Raw command lines were not serialized; Windows provider ownership partly unverified.',
              'production_secret_created': False, 'secret_values_recorded': False}
    (ROOT / 'reports/institution_v2n_secret_audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'key_locations': len(keys), 'URI_pattern_findings': len(findings)}))


if __name__ == '__main__': main()
