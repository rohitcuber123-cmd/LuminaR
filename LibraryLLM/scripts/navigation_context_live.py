"""Read-only normal login audit. Credentials exist only in process memory."""
import getpass
import json
import sys
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'

def main():
    phase = sys.argv[1]
    email = input('Development account email: ')
    password = getpass.getpass('Development password (runtime only): ')
    result = {}
    with httpx.Client(timeout=90) as client:
        for port in (8002, 8088):
            base = f'http://127.0.0.1:{port}'
            login = client.post(base + '/auth/login', json={'email': email, 'password': password})
            login.raise_for_status()
            headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
            def read(path, method='GET', body=None):
                response = client.request(method, base + path, headers=headers, json=body)
                return {'method': method, 'path': path, 'status': response.status_code, 'body': response.json()}
            result[str(port)] = {
                'identity': {k: v for k, v in login.json()['user'].items() if k in ('user_id', 'name', 'role', 'is_verified', 'is_email_verified', 'is_active')},
                'memberships': read('/me/libraries?offset=0&limit=100'),
                'context': read(f'/libraries/{TEST}/context'),
                'home': read(f'/libraries/{TEST}/catalogue/home'),
                'recommendations': read(f'/libraries/{TEST}/catalogue/recommendations', 'POST', {'work_ids': [], 'limit': 10}),
            }
    (ROOT / f'reports/navigation_context_live_{phase}.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({port: {name: entry.get('status', 'login identity') for name, entry in data.items()} for port, data in result.items()}, indent=2))

if __name__ == '__main__':
    main()
