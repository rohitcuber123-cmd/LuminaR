# Library route 404 — resolved stale runtime

Before edits, normal login and My Libraries Open Library reached /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae on frontend 5173 and displayed Unable to load this library catalogue / Not Found. Direct access produced the same result. Membership discovery and /context succeeded with HTTP 200. GET /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue/home also succeeded with LIBRARY_LOCAL / 150.

Exact failing request: POST http://127.0.0.1:8002/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue/recommendations (frontend proxy path /api/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue/recommendations), HTTP 404, body {"detail":"Not Found"}. The Home loader first obtains local Home data, then filters global recommendation candidate IDs through this scoped read route. This second read was missing in the running old Core.

OpenAPI comparison before restart: Core 8002 did not register catalogue/recommendations; Core 8088 did. Both had catalogue/home and me/libraries. The process had been started before the recommendation route was added and ran without reload. The normal Vite configuration correctly proxied /api to 8002; review 5182 used its separate 8088 override. Internal navigation ports were not the cause.

The identified normal Core was restarted with backend.main:app, the same host/port, and current source. After a runtime interruption while continuing the task, normal 5173/8002 and review 5182/8088 were restored with these same configurations. Current scoped reads are 200 on both Core instances; real browser Home and child navigation pass on both frontends. No compatibility endpoint or global fallback masking was added. No backend product code changed.

Evidence: navigation_context_route_baseline.json, navigation_context_live_before.json, navigation_context_live_after.json, navigation_context_browser.json and navigation_context_screenshots/before-5173-error.png. Current PRIOR_404_REPRODUCIBLE=NO; it was YES before restart.
