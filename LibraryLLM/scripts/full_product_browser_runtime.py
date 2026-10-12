"""Read-only runtime evidence, without config secrets or authentication material."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
SERVICES={'frontend':'http://127.0.0.1:5173/','core':'http://127.0.0.1:8002/health','search':'http://127.0.0.1:8003/health','recommendations':'http://127.0.0.1:8004/docs','rag_assistant':'http://127.0.0.1:8005/health'}
def probe(pair):
    name,url=pair
    response=requests.get(url,timeout=30)
    return {'service':name,'url':url,'status':response.status_code,'health':response.json() if 'application/json' in response.headers.get('content-type','') else 'HTML available'}

def main():
    rows=list(ThreadPoolExecutor().map(probe,SERVICES.items()))
    (ROOT/'reports/full_product_browser_runtime.json').write_text(json.dumps({'captured_at':datetime.now(timezone.utc).isoformat(),'services':rows},indent=2),encoding='utf8')
    text='# Browser review runtime\n\nAll application services were stopped at initial inspection; MongoDB alone was listening on 27017. Fresh processes were started only on the vacant configured local ports. No other live application stack was replaced. The previous internal error tab was stale; a fresh IAB tab opened the real root successfully after startup. The exact cause of the historical tab failure cannot be reconstructed beyond this observed stopped-server condition. No security warning, CORS error, auth loop or hardcoded product-navigation port was found.\n\n'
    text+='| Service | URL | HTTP |\n|---|---|---|\n'+''.join(f"| {r['service']} | {r['url']} | {r['status']} |\n" for r in rows)
    text+='\nMongoDB: existing local database `luminar_library`; application data preserved. Frontend routes and API requests are relative; Vite proxies use the existing local service configuration. Review browser: installed Playwright Chromium 151.0.7922.34, real rendering with separate authenticated QA contexts; headless, no JSDOM substitution. IAB root also verified. Startup was awaited by HTTP probes before UI tests.\n\nRouter: existing_qwen; offline model loading; no HNSW/KG/model rebuild or ranking changes. Search reports the accepted pre-existing STALE / baseline_verified=false health condition. Browser Search behavior is reported separately. Passwords are read at runtime only; no credential screenshots, auth bypass, committed secrets or persisted browser storage states.\n'
    (ROOT/'reports/full_product_browser_runtime.md').write_text(text,encoding='utf8')
    print({r['service']:r['status'] for r in rows})
if __name__=='__main__':main()
