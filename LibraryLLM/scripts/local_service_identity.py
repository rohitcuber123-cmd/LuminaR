"""Best-effort public fingerprints for existing loopback HTTP listeners."""
from http.client import HTTPConnection, HTTPException
import json


API_INFO = {
    'core': ('LuminaR Library API', '1.0.0'),
    'search': ('LuminaR Search API', '1.0.0'),
    'recommendation': ('LuminaR Recommendation API', '2.0.0'),
    'rag': ('LuminaR RAG API', '1.0.0'),
}
MAX_FINGERPRINT_BYTES = 2 * 1024 * 1024


def matches_service(name, port):
    """Match the advertised kind and API version, without establishing ownership."""
    connection = HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request('GET', '/' if name == 'frontend' else '/openapi.json')
        response = connection.getresponse()
        if response.status != 200:
            return False
        body = response.read(MAX_FINGERPRINT_BYTES + 1)
        if len(body) > MAX_FINGERPRINT_BYTES:
            return False
        if name == 'frontend':
            return all(marker in body for marker in (
                b'<title>LuminaR ', b'"/@vite/client"', b'"/src/main.tsx"',
            ))
        document = json.loads(body)
        if not isinstance(document, dict) or not isinstance(document.get('info'), dict):
            return False
        info = document['info']
        return (info.get('title'), info.get('version')) == API_INFO[name]
    except (OSError, HTTPException, ValueError, RecursionError):
        return False
    finally:
        connection.close()
