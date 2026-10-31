# Complete reviewed transport contract

All bytes of the following modules are pinned, including function bodies, imports, declarations, state, retry policy and module-level executable code:

| Module | SHA256 |
|---|---|
| `frontend/src/lib/libraryIntelligence.ts` | `812b2fac2f6da3589f26c988a5922fe3814f758e0a609cdfdea33fc3218ed9da` |
| `frontend/src/lib/institutions.ts` | `d306300550899c9756c34766c29a7a3a2fa3737ac0578c9e629e1781d5d6603d` |
| `frontend/src/lib/api.ts` | `a62df6a8acc949f7544acef00a5147faa515537ff5e75c9389880fd7e7b8a184` |

libraryIntelligence calls institutionApi, which imports request/ApiError from api.ts. api.ts has no further static imports. Pinning all three modules closes that reviewed transport dependency chain, instead of protecting only one export line while permitting body/module changes. This intentionally requires explicit review for future changes to the shared transport modules; it does not freeze the UI page. Their original current bytes are unchanged in O.2.

The reviewed implementation preserves exact tenant GET/POST paths, abort signals, no-store requests, session matching before/after requests, per-session/per-tenant ordering, current-access revalidation on denial and bounded read retries. Build commands are not automatically retried. No frontend operator infrastructure endpoint or Mongo credential is introduced. Canonical UUID validity/current membership remain checked by backend authority.

Tests mutate actual helper bodies, multiline bodies, institutionApi dependency calls and generic API prefix; each fails the real proposed guard. A scope change in route parameters, request UUID, selected context or build helper similarly fails. The compiler and installed React/router/stores are trusted dependencies beyond this transport source chain; package/config/store preservation and full behavior checks are separately required.
