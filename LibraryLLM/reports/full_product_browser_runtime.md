# Browser review runtime

All application services were stopped at initial inspection; MongoDB alone was listening on 27017. Fresh processes were started only on the vacant configured local ports. No other live application stack was replaced. The previous internal error tab was stale; a fresh IAB tab opened the real root successfully after startup. The exact cause of the historical tab failure cannot be reconstructed beyond this observed stopped-server condition. No security warning, CORS error, auth loop or hardcoded product-navigation port was found.

| Service | URL | HTTP |
|---|---|---|
| frontend | http://127.0.0.1:5173/ | 200 |
| core | http://127.0.0.1:8002/health | 200 |
| search | http://127.0.0.1:8003/health | 200 |
| recommendations | http://127.0.0.1:8004/docs | 200 |
| rag_assistant | http://127.0.0.1:8005/health | 200 |

MongoDB: existing local database `luminar_library`; application data preserved. Frontend routes and API requests are relative; Vite proxies use the existing local service configuration. Review browser: installed Playwright Chromium 151.0.7922.34, real rendering with separate authenticated QA contexts; headless, no JSDOM substitution. IAB root also verified. Startup was awaited by HTTP probes before UI tests.

Router: existing_qwen; offline model loading; no HNSW/KG/model rebuild or ranking changes. Search reports the accepted pre-existing STALE / baseline_verified=false health condition. Browser Search behavior is reported separately. Passwords are read at runtime only; no credential screenshots, auth bypass, committed secrets or persisted browser storage states.
