import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from scripts.local_service_identity import matches_service


@pytest.mark.parametrize('name,path,status,body,expected', [
    ('core', '/openapi.json', 200,
     {'info': {'title': 'LuminaR Library API', 'version': '1.0.0'}}, True),
    ('search', '/openapi.json', 200,
     {'info': {'title': 'LuminaR Library API', 'version': '1.0.0'}}, False),
    ('recommendation', '/openapi.json', 200,
     {'info': {'title': 'LuminaR Recommendation API', 'version': '1.0.0'}}, False),
    ('rag', '/openapi.json', 302, {}, False),
    ('core', '/openapi.json', 200, b'foreign HTTP listener', False),
    ('frontend', '/', 200, b'<title>LuminaR dev</title> "/@vite/client" "/src/main.tsx"', True),
    ('frontend', '/', 200, b'<title>Vite test</title> "/@vite/client" "/src/main.tsx"', False),
])
def test_loopback_fingerprint(name, path, status, body, expected):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status if self.path == path else 404)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
        thread.start()
        try:
            assert matches_service(name, server.server_port) is expected
        finally:
            server.shutdown()
            thread.join()
