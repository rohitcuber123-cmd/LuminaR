# 04 — AUTHENTICATION, AUTHORIZATION & ACCESS CONTROL (RBAC)

## 1. Authentication Infrastructure

User authentication in LuminaR provides cryptographic identity verification while decoupling platform identity from tenant-specific authority.

### 1.1 Complete Authentication Stack

| Component | Implementation File | Underlying Technology | Configuration / Parameters | Code Reference |
|---|---|---|---|---|
| **Password Hashing** | `backend/services/auth_service.py` | `bcrypt` (C-optimized) | `bcrypt.gensalt()`, max 72 bytes constraint | [auth_service.py:L21-34](file:///d:/SDC/LibraryLLM/backend/services/auth_service.py#L21-L34) |
| **Email OTP Verification** | `backend/services/auth_service.py` | `bcrypt` | 6-digit numeric OTP, bcrypt hashed in DB, 15m expiry | [auth_service.py:L36-42](file:///d:/SDC/LibraryLLM/backend/services/auth_service.py#L36-L42) |
| **Token Signing** | `backend/utils/jwt_utils.py` | `python-jose` | Algorithm: `HS256`, Secret: `JWT_SECRET_KEY` | [jwt_utils.py:L13-39](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L13-L39) |
| **Token Lifetime** | `backend/utils/jwt_utils.py` | Timed UTC expiry | 30 minutes for staff (`ADMIN`/`LIBRARIAN`), 60 minutes for `GENERAL_USER` | [jwt_utils.py:L22-24](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L22-L24) |
| **Session Revocation Ledger** | `backend/services/login_sessions.py` | `sqlite3` (`rag/private_sessions.sqlite`) | Table: `revoked_sessions (sid PRIMARY KEY, expires REAL)` | [login_sessions.py:L9-35](file:///d:/SDC/LibraryLLM/backend/services/login_sessions.py#L9-L35) |
| **Auth Rate Limiting** | `backend/utils/auth_rate_limit.py` | In-memory token bucket | 5 failed attempts per IP/account window | [auth.py:L67-68](file:///d:/SDC/LibraryLLM/backend/routes/auth.py#L67-L68) |

### 1.2 JWT Claims Architecture

When a user logs in via `POST /auth/login` or `POST /auth/staff-login`, the backend issues a signed JSON Web Token with the following payload structure:
```json
{
  "sub": "1",
  "email": "admin@luminar.org",
  "role": "ADMIN",
  "sid": "7b892a01d3e8461a9f14cf7982e0114f",
  "iat": 1728820800,
  "exp": 1728822600
}
```

#### Architectural Security Rationale:
1. `sub`: Contains the canonical numeric identifier of the user in `users_collection`.
2. `sid`: A unique UUID4 session ID. On logout (`POST /auth/logout`), the `sid` is inserted into `revoked_sessions` in `private_sessions.sqlite`. Any subsequent request presenting that token is rejected immediately ([jwt_utils.py:L54-56](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L54-L56)), solving the standard "stateless JWT cannot be invalidated" vulnerability.
3. `role`: Represents the legacy global account category (`GENERAL_USER`, `LIBRARIAN`, `ADMIN`). **Crucially, this role never grants institutional authority.**

---

## 2. Decoupling Global Account Roles from Library Tenancy

A classic flaw in naive multi-tenant systems is checking `user.role == 'ADMIN'` and assuming the user has administrative privileges across all tenant libraries. 

### 2.1 The Deprecation of Global Roles
In LuminaR, the global role is explicitly disabled from granting any tenant management authority:
- Code reference: [backend/dependencies.py:L27-32](file:///d:/SDC/LibraryLLM/backend/dependencies.py#L27-L32):
  ```python
  def require_roles(*allowed_roles):
      """Deprecated: User.role never grants tenant or platform management authority."""
      def denied(current_user=Depends(get_current_user)):
          raise HTTPException(403, "Legacy account roles do not grant management authority.")
      return denied
  ```
- **Consequence**: An account with global role `ADMIN` has **zero automatic authority** inside a private library workspace. Administrative authority exists solely through an explicit `institution_memberships` record for that specific `library_id`.

---

## 3. Dynamic Per-Request Authorization (`institution_dependencies.py`)

All tenant routes inject reusable FastAPI dependencies from `backend/institution_dependencies.py`:

```
   [ Incoming Request ]
          │
   FastAPI Route: /libraries/{library_id}/...
          │
          ├── Depends(get_current_user) -> decodes JWT, verifies signature & sid
          │
          └── Depends(require_library_role / require_library_staff / require_library_membership)
                    │
                    ├── 1. actor_id(current_user) -> int(user['sub'])
                    │
                    ├── 2. resolve_library_membership(library_id, current_user):
                    │         ├── db['institution_libraries'].find_one({'library_id': id, 'status': 'ACTIVE'})
                    │         │     └── If None -> 404 "Library not found."
                    │         ├── require_readable(library_id) -> checks mutation lock
                    │         │     └── If locked -> 503 "Library update in progress."
                    │         └── db['institution_memberships'].find_one({'library_id': id, 'user_id': user_id, 'status': 'ACTIVE'})
                    │               └── If invitation grant -> verifies accepted proof in invitations
                    │
                    ├── 3. require_library_membership:
                    │         └── If membership is None -> 404 "Library resource not found." [CONCEALMENT]
                    │
                    └── 4. require_library_role(library_id, current_user, *roles):
                              └── If membership['role'] not in roles -> 403 "Insufficient library permissions."
```

### 3.1 Defense-in-Depth: Information Concealment (404 vs 403)

Standard security guidance requires that private resources should not leak their existence to unauthorized callers:
- Code reference: [backend/institution_dependencies.py:L39-44](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L39-L44):
  ```python
  def require_library_membership(library_id, current_user, *, locked=False):
      library, membership = resolve_library_membership(library_id, current_user, locked=locked)
      if not membership:
          # Conceal the existence of protected resources from outsiders, including global admins.
          raise HTTPException(404, 'Library resource not found.')
      return library, membership
  ```
- If an unauthorized user guesses or observes a UUID for Library X, sending a request returns `404 Not Found`, giving zero indication whether the library or asset exists.

---

## 4. Platform Administration Isolation (`platform_dependencies.py`)

LuminaR features a dedicated Platform Console (`/platform/*`) for server operators. A critical security verification is: **Can a platform administrator view or manipulate private library data?**

### 4.1 Explicit Platform Authority Verification
- Code reference: [backend/platform_dependencies.py:L8-24, L42-46](file:///d:/SDC/LibraryLLM/backend/platform_dependencies.py#L8-L24#L42-L46):
  ```python
  def platform_assignments(user_id):
      from backend.database.mongodb import db
      now = datetime.now(timezone.utc)
      result = []
      for row in db['platform_role_assignments'].find({'user_id': int(user_id), 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE'}):
          # An imported legacy role or incomplete grant document is never authority.
          if not all(isinstance(row.get(key),str) and row[key].strip() for key in ('approval_ref','approved_by')) or not isinstance(row.get('approved_at'),datetime):
              continue
          # Validates approved_at <= now and (expires_at is None or expires_at > now)
          result.append(row)
      return result

  def require_platform_admin(payload=Depends(get_current_user)):
      identity = current_account(payload)
      if not platform_assignments(identity['sub']):
          raise HTTPException(403, 'An active, explicitly approved PLATFORM_ADMIN assignment is required.')
      return identity
  ```
- **Requirements for Platform Authority**:
  1. Record in `platform_role_assignments` with `role: 'PLATFORM_ADMIN'`.
  2. Non-empty string fields for `approval_ref` and `approved_by`.
  3. Valid `approved_at` datetime in the past.
  4. Unexpired `expires_at` timestamp.

### 4.2 Strict Tenant Boundary Against Platform Admins
- Platform admins can manage platform-level account status (`POST /platform/accounts`), view directory status (`GET /platform/libraries`), or suspend/restore a tenant (`POST /platform/libraries/{id}/suspend`).
- **Platform admins CANNOT access library-scoped APIs** (`/libraries/{id}/inventory`, `/assets`, `/lending`, `/intelligence`). Because `institution_dependencies.py` checks `institution_memberships`, a platform administrator without a membership record receives `404 Not Found` when attempting to access private library endpoints ([tests/institution_v2h/test_controls.py:L20-22](file:///d:/SDC/LibraryLLM/tests/institution_v2h/test_controls.py#L20-L22)).

---

## 5. Comprehensive RBAC Permissions Matrix

The following table reflects the code-verified authorization enforcement across every major system operation:

| System Operation | Route Endpoint | Library Owner | Library Admin | Library Librarian | Library General User | Unauthenticated / Outsider | Platform Admin (Without Membership) | Enforcement Code Location |
|---|---|---|---|---|---|---|---|---|
| **Register Library** | `POST /libraries/register` | N/A | N/A | N/A | Allowed (Becomes Owner) | 401 | Allowed (Becomes Owner) | `institution_service.py:L58` |
| **Join Public Library** | `POST /libraries/{id}/join` | Already Member | Already Member | Already Member | Allowed (Becomes Member) | 401 | Allowed (Becomes Member) | `institution_service.py:L148` |
| **Join Private Library** | `POST /libraries/{id}/join` | Already Member | Already Member | Already Member | Allowed (With Valid Code) | 401 | Allowed (With Valid Code) | `institution_service.py:L159` |
| **View Library Context** | `GET /libraries/{id}/context` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `institutions.py:L44` |
| **Rotate Access Code** | `PUT /libraries/{id}/access-code` | Allowed | Allowed | Allowed | 403 | 401 | 404 | `institutions.py:L65` |
| **Change Access Mode** | `PUT /libraries/{id}/access` | Allowed | Allowed | 403 | 403 | 401 | 404 | `institutions.py:L70` |
| **Invite Staff Member** | `POST /libraries/{id}/invitations` | Allowed | Allowed (Librarian only) | 403 | 403 | 401 | 404 | `institutions.py:L90` |
| **Invite Admin Member** | `POST /libraries/{id}/invitations` | Allowed | 403 (Owner only) | 403 | 403 | 401 | 404 | `institution_service.py:L230` |
| **List Staff & Members** | `GET /libraries/{id}/memberships` | Allowed | Allowed | 403 | 403 | 401 | 404 | `institutions.py:L75` |
| **Update Member Role** | `PATCH /libraries/{id}/memberships/{m_id}` | Allowed | Allowed (Librarian/User) | 403 | 403 | 401 | 404 | `institution_service.py:L375` |
| **Demote/Remove Owner** | `PATCH /libraries/{id}/memberships/{m_id}` | 403 (Blocked) | 403 (Blocked) | 403 | 403 | 401 | 404 | `institution_service.py:L381` |
| **Demote Last Admin** | `PATCH /libraries/{id}/memberships/{m_id}` | 409 (Blocked) | 409 (Blocked) | 403 | 403 | 401 | 404 | `institution_service.py:L391` |
| **View Audit Trail** | `GET /libraries/{id}/audit` | Allowed | Allowed | 403 | 403 | 401 | 404 | `institutions.py:L110` |
| **Create Inventory Book** | `POST /libraries/{id}/inventory/books` | Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_inventory.py:L21` |
| **Import Catalog CSV** | `POST /libraries/{id}/inventory/imports/apply`| Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_inventory.py:L73` |
| **Withdraw Inventory Book**| `DELETE /libraries/{id}/inventory/books/{b_id}`| Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_inventory.py:L46` |
| **Upload Digital Asset** | `POST /libraries/{id}/assets` | Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_assets.py:L33` |
| **View Member Asset** | `GET /libraries/{id}/assets/{asset_id}` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `library_assets.py:L46` |
| **View Staff-Only Asset**| `GET /libraries/{id}/assets/{asset_id}` | Allowed | Allowed | Allowed | 404 (Concealed) | 401 | 404 | `library_asset_service.py:L110` |
| **Request Borrow** | `POST /libraries/{id}/lending/borrow-requests` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `library_lending.py:L51` |
| **Approve Borrow Request**| `POST /.../borrow-requests/{req_id}/approve` | Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_lending.py:L87` |
| **Return Book Request** | `POST /libraries/{id}/loans/{loan_id}/return` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `library_lending.py:L92` |
| **Confirm Book Return** | `POST /.../return-requests/{req_id}/confirm` | Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_lending.py:L97` |
| **Reserve Book Holding** | `POST /libraries/{id}/reservations` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `library_reservations_fees.py:L26` |
| **Waive/Adjust Fee** | `POST /libraries/{id}/staff/fees/{fee_id}/waive`| Allowed | Allowed | Allowed | 403 | 401 | 404 | `library_reservations_fees.py:L93` |
| **Trigger Search/KG Build**| `POST /libraries/{id}/intelligence/builds` | Allowed | Allowed | 403 | 403 | 401 | 404 | `library_intelligence.py` |
| **Query Semantic Search** | `GET /libraries/{id}/catalogue/search` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `library_intelligence_api.py:L19` |
| **Query Document RAG** | `POST /libraries/{id}/assets/{asset_id}/rag` | Allowed | Allowed | Allowed | Allowed | 401 | 404 | `library_asset_routes.py:L40` |
| **Suspend Library** | `POST /platform/libraries/{id}/suspend` | 403 | 403 | 403 | 403 | 401 | Allowed | `platform.py:L39` |

---

## 6. Summary for Project Review

1. **Identity vs. Authority**: Authentication grants proof of identity (`sub`), but zero institutional authority. Authority is evaluated per-request against MongoDB.
2. **Immediate Revocation**: Revoking a membership takes effect on the user's very next HTTP request without waiting for token expiration.
3. **No Direct Object Reference (IDOR)**: Passing a forged or foreign `library_id` in the URL fails `require_library_membership` and returns `404 Not Found`.
4. **Platform Isolation**: Platform administrators cannot read private library books, assets, or loan records without explicit institutional membership.
